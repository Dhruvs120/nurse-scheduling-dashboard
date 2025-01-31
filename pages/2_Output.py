import streamlit as st
import pandas as pd
from functions import calendar_creator, handle_view_change, create_excel_schedule
import plotly.express as px

# Configure page
st.set_page_config(page_title="Schedule Output", layout="wide")

# Validate state
if not st.session_state.get('schedule_generated', False):
    st.warning("⚠️ Please generate a schedule in the Submit page first.")
    st.stop()

# Create tabs
tab1, tab2 = st.tabs(["Weekly Schedule", "Cost Analysis"])

try:
    with tab1:
        # Get model and task data
        model = st.session_state.model
        task_sheet_df = pd.read_excel(st.session_state.input_file, sheet_name='Tasks')

        # Header
        st.markdown("### Weekly Schedule")
        
        # Calendar type selection with default views
        calendar_type = st.selectbox(
            "Select Calendar View",
            ("Total calendar", "Shift calendar", "Task calendar"),
            key="calendar_type_selector"
        )

        # Add legend
        st.markdown("### Legend")
        legend_cols = st.columns(5)
        with legend_cols[0]:
            st.markdown("<div style='background-color: #B8CCE4; padding: 8px; border-radius: 4px; font-size: 14px;'>Regular Shift</div>", unsafe_allow_html=True)
        with legend_cols[1]:
            st.markdown("<div style='background-color: #FF9999; padding: 8px; border-radius: 4px; font-size: 14px;'>Break</div>", unsafe_allow_html=True)
        with legend_cols[2]:
            st.markdown("<div style='background-color: #90EE90; padding: 8px; border-radius: 4px; font-size: 14px;'>Handover</div>", unsafe_allow_html=True)
        with legend_cols[3]:
            st.markdown("<div style='background-color: #FFD700; padding: 8px; border-radius: 4px; font-size: 14px;'>Task</div>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        # Initialize default views for each calendar type
        if 'last_calendar_type' not in st.session_state:
            st.session_state.last_calendar_type = calendar_type
        
        # Only update view if calendar type changes
        if calendar_type != st.session_state.get('last_calendar_type'):
            if calendar_type == "Total calendar":
                st.session_state.calendar_view = 'resourceTimelineWeek'
            elif calendar_type == "Shift calendar":
                st.session_state.calendar_view = 'resourceTimelineDay'
            else:  # Task calendar
                st.session_state.calendar_view = 'resourceTimelineDay'
            
            st.session_state.last_calendar_type = calendar_type
            st.rerun()

        # Create calendar with appropriate type
        calendar, nurse_shifts, break_shifts, overdracht1, overdracht2 = calendar_creator(
            model=model,
            calendar_type=calendar_type.split()[0].lower(),  # "total", "shift", or "task"  
            task_sheet_df=task_sheet_df
        )

        st.write(calendar)

        # Handle calendar view changes from user interaction
        if calendar:
            handle_view_change(calendar)

        # Download section
        st.markdown("### Download Options")
        col1, col2 = st.columns(2)
        
        with col1:
            excel_file = create_excel_schedule(nurse_shifts, break_shifts, overdracht1, overdracht2)
            st.download_button(
                label="📥 Download Schedule (Excel)",
                data=excel_file,
                file_name="nurse_schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download the complete schedule as an Excel file"
            )

    with tab2:
        # Cost Analysis Section
        st.markdown("### Cost Analysis")
        
        # Calculate costs
        daily_costs = [0] * 7
        total_costs = 0
        
        for var in model.getVars():
            if 'salary_per_interval' in var.varName and var.x > 0:
                try:
                    interval = int(var.varName.split('[')[1].split(']')[0])
                    day_index = interval // 96  # 96 intervals per day
                    if 0 <= day_index < 7:
                        daily_costs[day_index] += var.x
                        total_costs += var.x
                except (IndexError, ValueError):
                    continue

        # Display cost metrics
        cost_cols = st.columns(3)
        
        with cost_cols[0]:
            avg_daily = sum(daily_costs) / 7
            st.metric("Average Daily Cost", f"€{avg_daily:,.2f}")
        
        with cost_cols[1]:
            st.metric("Total Weekly Cost", f"€{total_costs:,.2f}")
            
        with cost_cols[2]:
            highest_cost = max(daily_costs)
            st.metric("Highest Daily Cost", f"€{highest_cost:,.2f}")

        # Daily cost breakdown
        st.markdown("### Daily Cost Breakdown")
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Create columns for cost display
        cost_columns = st.columns(7)
        for idx, (day, cost) in enumerate(zip(weekdays, daily_costs)):
            with cost_columns[idx]:
                st.metric(day, f"€{cost:,.2f}")
                
        # Cost distribution chart
        st.markdown("### Cost Distribution")
        
        cost_df = pd.DataFrame({
            'Day': weekdays,
            'Cost': daily_costs
        })
        
        fig = px.bar(cost_df, x='Day', y='Cost',
                    title='Daily Cost Distribution',
                    labels={'Cost': 'Cost (€)'},
                    color='Cost')
        st.plotly_chart(fig, use_container_width=True)
        
        
        # Activity measures
        total_nurses_present_value = model.getVarByName("total_nurses_present").X
        total_nurses_with_tasks_value = model.getVarByName("total_nurses_tasks").X
        total_nurses_active_value = model.getVarByName("total_nurses_active").X

        # Calculate the ratios
        if total_nurses_present_value > 0:
            tasks_ratio = total_nurses_with_tasks_value / total_nurses_present_value
            active_ratio = total_nurses_active_value / total_nurses_present_value
        else:
            tasks_ratio = 0
            active_ratio = 0

        # Display the results
        st.markdown("### Activity Measures")
        activity_cols = st.columns(2)

        with activity_cols[0]:
            st.metric("Ratio of nurses working on tasks", f"{tasks_ratio:.2f}")

        with activity_cols[1]:
            st.metric("Ratio of nurses actively working (including handovers)", f"{active_ratio:.2f}")

except Exception as e:
    st.error(f"❌ Error displaying schedule: {str(e)}")
    st.stop()