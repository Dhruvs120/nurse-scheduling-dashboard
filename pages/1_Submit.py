import streamlit as st
from NRP_OBP_D import main
import os
import pandas as pd
from datetime import time

st.set_page_config(page_title="Nurse Rostering Problem", page_icon="👩‍⚕️", layout="wide")

col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    st.image("images/amsterdam-umc-universitair-medische-centra-logo-vector-2_black.png", width=400)
with col4:
    st.image("images/VU_logo_black.png", width=400)
    
preset_options = ["Kostwinner zonder kinderen", "Kostwinner met kinderen", "Young Professional",
                "Kids First", "Mantelzorger", "Vrije vogel", "Student"]


if 'nurse_entries' not in st.session_state:
    st.session_state.nurse_entries = []

if 'personnel_df_final' not in st.session_state:
    st.session_state.personnel_df_final = pd.DataFrame(columns=[
        "Nurse_ID", "Monday Start", "Monday End", "Tuesday Start", "Tuesday End", 
        "Wednesday Start", "Wednesday End", "Thursday Start", "Thursday End", 
        "Friday Start", "Friday End", "Saturday Start", "Saturday End", 
        "Sunday Start", "Sunday End"
    ])

# Title
st.markdown("<h2>Schedule Data Input</h2>", unsafe_allow_html=True)

# Create tabs
tab1, tab2 = st.tabs(["Upload Excel", "Manual Entry"])

with tab1:
    # Template Download Button
    template_path = "Hospital_Data_template.xlsx"
    if os.path.exists(template_path):
        with open(template_path, "rb") as file:
            template_bytes = file.read()
        st.download_button(
            label="📥 Download Template File",
            data=template_bytes,
            file_name="Hospital_Data_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download the Excel template file to see the required format"
        )

    # Initialize session state
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    if 'schedule_generated' not in st.session_state:
        st.session_state.schedule_generated = False
    if 'model' not in st.session_state:
        st.session_state.model = None

    # Instructions
    st.markdown("""
    ### Instructions:
    1. Upload your Excel file with the schedule data
    2. Set the hourly rates for day and night shifts
    3. Confirm the file format
    4. Click on *Generate Schedule* to generate the schedule
    """)

    # Create form
    with st.form("schedule_form"):
        # File upload
        uploaded_file = st.file_uploader(
            "Upload Excel Schedule File", 
            type=['xls', 'xlsx'],
            help="Upload your schedule data in Excel format"
        )

        # Rate inputs in columns
        col1, col2 = st.columns(2)
        with col1:
            day_rate = st.number_input(
                "Day Shift Rate (€/hour)",
                min_value=0.0,
                value=15.0,
                step=0.5,
                help="Hourly rate for day shifts"
            )
        with col2:
            night_rate = st.number_input(
                "Night Shift Rate (€/hour)",
                min_value=0.0,
                value=20.0,
                step=0.5,
                help="Hourly rate for night shifts"
            )

        # Format confirmation
        st.markdown("### File Format Confirmation")
        agree = st.checkbox(
            "I confirm the input file follows the required format",
            help="Make sure your file follows the template structure"
        )
        
        # Time limit input
        time_limit = st.number_input(
            "Time Limit (seconds)",
            min_value=1,
            value=300,
            step=1,
            help="Set the time limit for the scheduling algorithm"
        )

        # Submit button
        submitted = st.form_submit_button("Generate Schedule")

        # Form processing
        if submitted:
            if not uploaded_file:
                st.error("⚠️ Please upload an input file")
            elif not agree:
                st.warning("⚠️ Please confirm the input file format")
            else:
                with st.spinner('Generating optimal schedule...'):
                    try:
                        model_result = main(uploaded_file, day_rate, night_rate, "only", time_limit)
                        
                        # Check if model is infeasible
                        if model_result.Status == 3:  # GRB.Status.INFEASIBLE
                            st.error("❌ The scheduling model is infeasible. Please check your input and try again.")
                            st.session_state.model = None
                            st.session_state.form_submitted = False
                            st.session_state.schedule_generated = False
                        else:
                            st.session_state.model = model_result
                            st.session_state.input_file = uploaded_file
                            st.session_state.personnel_df_final = pd.read_excel(uploaded_file, sheet_name="Personnel", engine="openpyxl")
                            st.session_state.form_submitted = True
                            st.session_state.schedule_generated = True
                            st.success("✅ Schedule generated successfully! Go to Output page to view results.")
                    except Exception as e:
                        st.error(f"❌ Error processing file: {str(e)}")
                        st.session_state.model = None
                        st.session_state.form_submitted = False
                        st.session_state.schedule_generated = False
with tab2:
    st.markdown("### Manual Data Entry")
    
    # File upload
    uploaded_file = st.file_uploader("Upload a file", type=["xls", "xlsx"], help="Upload an Excel file according to the template")
    if uploaded_file is not None:
        st.success("File uploaded successfully")
        
        personnel_df = pd.read_excel(uploaded_file, sheet_name="Personnel", engine="openpyxl")
        tasks_df = pd.read_excel(uploaded_file, sheet_name="Tasks", engine="openpyxl")
        if st.session_state.personnel_df_final.empty:
            st.session_state.personnel_df_final = personnel_df
        else:
            st.session_state.personnel_df_final = pd.concat([st.session_state.personnel_df_final, personnel_df], ignore_index=True)
        st.session_state.input_file = uploaded_file
    
    else:
        tasks_df = pd.DataFrame(columns=["Task", "Day", "Start", "End", "Duration (min)", "# Nurses"])
        personnel_df = pd.DataFrame(columns=[
            "Nurse_ID", "Monday Start", "Monday End", "Tuesday Start", "Tuesday End", 
            "Wednesday Start", "Wednesday End", "Thursday Start", "Thursday End", 
            "Friday Start", "Friday End", "Saturday Start", "Saturday End", 
            "Sunday Start", "Sunday End"
        ])

    # Rate inputs in columns
    col1, col2 = st.columns(2)
    with col1:
        day_rate = st.number_input(
            "Day Shift Rate (€/hour)",
            min_value=0.0,
            value=15.0,
            step=0.5,
            help="Hourly rate for day shifts"
        )
    with col2:
        night_rate = st.number_input(
            "Night Shift Rate (€/hour)",
            min_value=0.0,
            value=20.0,
            step=0.5,
            help="Hourly rate for night shifts"
        )
        
    # Format confirmation
    st.markdown("#### File Format Confirmation")
    agree = st.checkbox(
        "I confirm the input file follows the required format",
        help="Make sure your file follows the template structure"
    )
    
    # Time limit input
    time_limit = st.number_input(
        "Time Limit (seconds)",
        min_value=1,
        value=300,
        step=1,
        help="Set the time limit for the scheduling algorithm"
    )


   # Preset selection
    presets = {
        "Kostwinner zonder kinderen": {
            "Monday Start": time(7, 0), "Monday End": time(16, 0),
            "Tuesday Start": time(0, 0), "Tuesday End": time(0, 0),
            "Wednesday Start": time(7, 0), "Wednesday End": time(16, 0),
            "Thursday Start": time(0, 30), "Thursday End": time(8, 30),
            "Friday Start": time(16, 30), "Friday End": time(0, 30),
            "Saturday Start": time(0, 0), "Saturday End": time(0, 0),
            "Sunday Start": time(7, 0), "Sunday End": time(16, 0)
        },
        "Kostwinner met kinderen": {
            "Monday Start": time(7, 0), "Monday End": time(16, 0),
            "Tuesday Start": time(7, 0), "Tuesday End": time(16, 0),
            "Wednesday Start": time(0, 0), "Wednesday End": time(0, 0),
            "Thursday Start": time(0, 30), "Thursday End": time(8, 30),
            "Friday Start": time(16, 30), "Friday End": time(0, 30),
            "Saturday Start": time(0, 0), "Saturday End": time(0, 0),
            "Sunday Start": time(0, 0), "Sunday End": time(0, 0)
        },
        "Young Professional": {
            "Monday Start": time(7, 0), "Monday End": time(16, 0),
            "Tuesday Start": time(0, 0), "Tuesday End": time(0, 0),
            "Wednesday Start": time(7, 0), "Wednesday End": time(16, 0),
            "Thursday Start": time(0, 30), "Thursday End": time(8, 30),
            "Friday Start": time(16, 30), "Friday End": time(0, 30),
            "Saturday Start": time(0, 0), "Saturday End": time(0, 0),
            "Sunday Start": time(7, 0), "Sunday End": time(16, 0)
        },
        "Kids First": {
            "Monday Start": time(7, 0), "Monday End": time(16, 0),
            "Tuesday Start": time(0, 0), "Tuesday End": time(0, 0),
            "Wednesday Start": time(0, 0), "Wednesday End": time(0, 0),
            "Thursday Start": time(7, 0), "Thursday End": time(16, 0),
            "Friday Start": time(8, 0), "Friday End": time(16, 30),
            "Saturday Start": time(0, 0), "Saturday End": time(0, 0),
            "Sunday Start": time(0, 0), "Sunday End": time(0, 0)
        },
        "Mantelzorger": {
            "Monday Start": time(15, 0), "Monday End": time(23, 0),
            "Tuesday Start": time(15, 0), "Tuesday End": time(23, 0),
            "Wednesday Start": time(0, 0), "Wednesday End": time(0, 0),
            "Thursday Start": time(0, 0), "Thursday End": time(0, 0),
            "Friday Start": time(0, 0), "Friday End": time(0, 0),
            "Saturday Start": time(0, 0), "Saturday End": time(0, 0),
            "Sunday Start": time(17, 0), "Sunday End": time(1, 0)
        },
        "Vrije vogel": {
            "Monday Start": time(9, 0), "Monday End": time(18, 0),
            "Tuesday Start": time(0, 0), "Tuesday End": time(0, 0),
            "Wednesday Start": time(0, 0), "Wednesday End": time(0, 0),
            "Thursday Start": time(0, 0), "Thursday End": time(0, 0),
            "Friday Start": time(16, 30), "Friday End": time(0, 30),
            "Saturday Start": time(9, 0), "Saturday End": time(18, 0),
            "Sunday Start": time(0, 0), "Sunday End": time(0, 0)
        },
        "Student": {
            "Monday Start": time(9, 0), "Monday End": time(18, 0),
            "Tuesday Start": time(0, 0), "Tuesday End": time(0, 0),
            "Wednesday Start": time(0, 0), "Wednesday End": time(0, 0),
            "Thursday Start": time(0, 0), "Thursday End": time(0, 0),
            "Friday Start": time(16, 30), "Friday End": time(0, 30),
            "Saturday Start": time(9, 0), "Saturday End": time(18, 0),
            "Sunday Start": time(0, 0), "Sunday End": time(0, 0)
        }
    }
    
    st.markdown("---")
    
    st.markdown("#### Add Nurses with Preset")
    
    preset_options = list(presets.keys())

        # Edit Preset section at the top
    with st.expander("Edit Preset"):
        selected_preset = st.selectbox("Select a Preset", preset_options)
        if selected_preset:
            preset_times = presets[selected_preset]
            for day, time in preset_times.items():
                preset_times[day] = st.text_input(day, value=time)
            if st.button("Save Changes"):
                presets[selected_preset] = preset_times
                st.success(f"Preset '{selected_preset}' updated successfully!")

    # Create two columns
    col1, col2 = st.columns(2)

    # Add/Remove nurse entries
    with col1:
        if st.button("Add Nurse Entry"):
            st.session_state.nurse_entries.append({"preset": preset_options[0], "number": 1})
        
        if st.button("Remove Last Entry") and len(st.session_state.nurse_entries) > 0:
            st.session_state.nurse_entries.pop()

    # Submit nurses with presets
    with col2:
        if st.button("Submit Nurses with Presets"):
            all_new_nurses = []
            
            for entry in st.session_state.nurse_entries:
                st.success(f"{entry['number']} Nurse(s) added with {entry['preset']} preset")
                preset = entry["preset"]
                number_of_nurses = entry["number"]
                preset_values = presets[preset]
                
                start_nurse_id = len(st.session_state.personnel_df_final) + len(all_new_nurses) + 1
                
                for i in range(number_of_nurses):
                    new_nurse = {"Nurse_ID": start_nurse_id + i}
                    new_nurse.update(preset_values)
                    all_new_nurses.append(new_nurse)
            
            if all_new_nurses:
                new_nurses_df = pd.DataFrame(all_new_nurses)
                
                for col in new_nurses_df.columns:
                    if col in st.session_state.personnel_df_final.columns:
                        new_nurses_df[col] = new_nurses_df[col].astype(st.session_state.personnel_df_final[col].dtype)
                
                st.session_state.personnel_df_final = pd.concat([st.session_state.personnel_df_final, new_nurses_df], ignore_index=True)
                st.session_state.personnel_df_final['Nurse_ID'] = st.session_state.personnel_df_final['Nurse_ID'].astype(int)

    # Display preset nurse entries
    for i, entry in enumerate(st.session_state.nurse_entries):
        st.markdown(f"**Nurse Entry {i+1}**")
        entry["preset"] = st.selectbox(
            f"Choose a preset for Nurse {i+1}",
            preset_options,
            key=f"preset_{i}",
            help="Select a preset schedule for the nurse"
        )
        entry["number"] = st.number_input(
            f"Number of Nurses for Nurse {i+1}",
            min_value=1,
            value=1,
            key=f"number_{i}"
        )

    st.markdown("---")

    # Single nurse entry with a custom schedule
    st.markdown("#### Add Single Nurse with Custom Schedule")
    st.markdown("Time has to be in 15 minutes intervals")
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    single_schedule = pd.DataFrame(columns=[
        "Nurse_ID", "Monday Start", "Monday End", "Tuesday Start", "Tuesday End",
        "Wednesday Start", "Wednesday End", "Thursday Start", "Thursday End",
        "Friday Start", "Friday End", "Saturday Start", "Saturday End",
        "Sunday Start", "Sunday End"
    ])

    # Create columns for each day of the week
    cols = st.columns(len(days_of_week))
    for i, day in enumerate(days_of_week):
        with cols[i]:
            st.markdown(f"**{day}**")
            available = st.checkbox(f"Available", key=f"available_{day}", value=True)
            start_time = st.time_input(
                f"Start Time ({day})", 
                key=f"start_{day}", 
                value="00:00",
                disabled=not available
            )
            end_time = st.time_input(
                f"End Time ({day})", 
                key=f"end_{day}", 
                value="00:00",
                disabled=not available
            )

    # Button to add a single nurse with the custom schedule
    if st.button("Add Single Nurse"):
        # Create a new single schedule DataFrame for this submission
        new_schedule = pd.DataFrame(columns=single_schedule.columns)
        
        # Read current values from form
        for day in days_of_week:
            available = st.session_state[f"available_{day}"]
            start_time = st.session_state[f"start_{day}"]
            end_time = st.session_state[f"end_{day}"]
            
            new_schedule.at[0, f"{day} Start"] = start_time if available else "23:45"
            new_schedule.at[0, f"{day} End"] = end_time if available else "23:45"
        
        # Assign a new Nurse_ID based on current personnel count
        new_schedule.at[0, "Nurse_ID"] = len(st.session_state.personnel_df_final) + 1
        
        # Ensure datatypes match before concatenation
        for col in new_schedule.columns:
            if col in st.session_state.personnel_df_final.columns:
                new_schedule[col] = new_schedule[col].astype(st.session_state.personnel_df_final[col].dtype)
        
        # Concatenate with existing personnel data
        # If personnel_df_final is empty, assign new_schedule directly
        if st.session_state.personnel_df_final.empty:
            st.session_state.personnel_df_final = new_schedule
        else:
            st.session_state.personnel_df_final = pd.concat([st.session_state.personnel_df_final, new_schedule], ignore_index=True)

    # Button to generate schedule with current data
    if st.button("Generate Schedule"):
        if agree and not st.session_state.personnel_df_final.empty:
            temp_df = st.session_state.personnel_df_final.copy()
            
            # Create temporary Excel file
            with pd.ExcelWriter("temp_data.xlsx", engine='openpyxl') as writer:
                temp_df.to_excel(writer, sheet_name='Personnel', index=False)
                tasks_df.to_excel(writer, sheet_name='Tasks', index=False)

            with st.spinner('Generating optimal schedule...'):
                try:
                    model_result = main("temp_data.xlsx", day_rate, night_rate, "nothing", time_limit)
                    
                    # Check if model is infeasible
                    if model_result.Status == 3:  # GRB.Status.INFEASIBLE
                        st.error("❌ The scheduling model is infeasible. Please check your input and try again.")
                        st.session_state.model = None
                        st.session_state.form_submitted = False
                        st.session_state.schedule_generated = False
                    else:
                        st.session_state.model = model_result
                        st.session_state.form_submitted = True
                        st.session_state.schedule_generated = True
                        st.success("✅ Schedule generated successfully! Go to Output page to view results.")
                except Exception as e:
                    st.error(f"❌ Error processing data: {str(e)}")
                    st.session_state.model = None
                    st.session_state.form_submitted = False
                    st.session_state.schedule_generated = False
                finally:
                    # Clean up temporary file
                    os.remove("temp_data.xlsx")
        else:
            if not agree:
                st.warning("⚠️ Please confirm the input file format")
            else:
                st.error("Please add nurses before generating the schedule")
