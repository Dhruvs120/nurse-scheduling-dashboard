import streamlit as st
import streamlit_calendar as sc
from NRP_OBP_D import main
from datetime import datetime, timedelta
import xlsxwriter
from io import BytesIO

def handle_view_change(calendar_data):
    """Handle calendar view changes"""
    if calendar_data and 'view' in calendar_data:
        st.session_state.calendar_view = calendar_data['view']

@st.cache_resource  # Changed from cache_data to cache_resource for Gurobi model
def generate_schedule(uploaded_file, day_rate, night_rate):
    try:
        # Hier wordt het dan uitgevoerd
        return main(uploaded_file, day_rate, night_rate)
    except Exception as e:
        st.error(f"Error generating schedule: {str(e)}")
        return None

def handle_generate_click(uploaded_file, day_rate, night_rate):
    st.session_state.button_clicked = True

    # Create a container for the spinner to control its placement
    spinner_container = st.container()
    with spinner_container:
        with st.spinner('Generating optimal schedule...'):
            # Generate the schedule
            st.session_state.model = generate_schedule(uploaded_file, day_rate, night_rate)
            st.session_state.schedule_generated = True
            st.session_state.calendar_data = st.session_state.model

def create_excel_schedule(nurse_shifts, break_shifts, handover1, handover2):

    excel_buffer = BytesIO()
    workbook = xlsxwriter.Workbook(excel_buffer)
    
    # Define cell formats
    shift_format = workbook.add_format({'bg_color': '#B8CCE4'})  # Light blue for shifts
    break_format = workbook.add_format({'bg_color': '#FF9999'})  # Light red for breaks
    handover_format = workbook.add_format({'bg_color': '#90EE90'})  # Light green for handovers

    # Create a worksheet for each day
    for day in range(1, 8):
        worksheet = workbook.add_worksheet(f'Day {day}')
        
        # Write time interval headers
        for t in range(96):
            hour = str(t // 4).zfill(2)
            minute = str((t % 4) * 15).zfill(2)
            worksheet.write(0, t + 1, f'{hour}:{minute}')

        # Get all nurse IDs for this day and sort them
        nurse_ids = sorted(nurse_shifts.get(day, {}).keys())
        
        # Write nurse IDs and fill in their schedules
        for row, nurse_id in enumerate(nurse_ids):
            worksheet.write(row + 1, 0, f'Nurse {nurse_id}')
            
            # Fill in shifts
            if day in nurse_shifts and nurse_id in nurse_shifts[day]:
                for interval in nurse_shifts[day][nurse_id]:
                    worksheet.write(row + 1, interval + 1, '', shift_format)

                # Add breaks
                if day in break_shifts and nurse_id in break_shifts[day]:
                    for interval in break_shifts[day][nurse_id]:
                        worksheet.write(row + 1, interval + 1, '', break_format)

                # Add handovers
                if day in handover1 and nurse_id in handover1[day]:
                    for interval in handover1[day][nurse_id]:
                        worksheet.write(row + 1, interval + 1, '', handover_format)
                if day in handover2 and nurse_id in handover2[day]:
                    for interval in handover2[day][nurse_id]:
                        worksheet.write(row + 1, interval + 1, '', handover_format)

        # Set column widths
        worksheet.set_column(0, 0, 10)  # Width for nurse ID column
        worksheet.set_column(1, 96, 6)  # Width for time columns

    workbook.close()
    excel_buffer.seek(0)
    return excel_buffer

def get_base_calendar_options(calendar_type):
    """Create base calendar options"""
    return {
        "editable": True,
        "selectable": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "resourceTimelineDay,resourceTimelineWeek,dayGridMonth",
        },
        "initialView": st.session_state.calendar_view,
        "resourceGroupField": "task" if calendar_type == "task" else "nurse_id",
        "slotMinTime": "00:00:00",
        "slotMaxTime": "24:00:00",
        "height": "auto"
    }

def calendar_creator(model, calendar_type, task_sheet_df):
    # Initialize data structures
    nurse_shifts = {}
    handover1 = {}
    handover2 = {}
    break_shifts = {}
    task_intervals = {}
    
    # Get base calendar options based on type
    base_options = get_base_calendar_options(calendar_type)

    # Add type-specific options
    if calendar_type == "task":
        base_options.update({
            "initialView": "resourceTimelineDay",
            "views": {
                "resourceTimelineDay": {"type": "resourceTimeline"},
                "resourceTimelineWeek": {"type": "resourceTimeline"},
                "dayGridMonth": {"type": "dayGrid"}
            },
            "resourceGroupField": "task"
        })
    elif calendar_type == "shift":
        base_options.update({
            "initialView": "resourceTimelineDay", 
            "views": {
                "resourceTimelineDay": {"type": "resourceTimeline"},
                "resourceTimelineWeek": {"type": "resourceTimeline"},
                "dayGridMonth": {"type": "dayGrid"}
            },
            "resourceGroupField": "nurse_id"
        })
    else: # total
        base_options.update({
            "initialView": "resourceTimelineWeek",
            "views": {
                "resourceTimelineDay": {"type": "resourceTimeline"},
                "resourceTimelineWeek": {"type": "resourceTimeline"},  
                "dayGridMonth": {"type": "dayGrid"}
            },
            "resourceGroupField": "nurse_id"
        })

    # Process model variables
    for var in model.getVars():
        if var.x == 1:
            if "nurse_active" in var.varName:
                nurse_id, interval = process_interval_var(var.varName)
                add_to_dict(nurse_shifts, nurse_id, interval)
            elif "handover1_active" in var.varName:
                nurse_id, interval = process_interval_var(var.varName)
                add_to_dict(handover1, nurse_id, interval)
            elif "handover2_active" in var.varName:
                nurse_id, interval = process_interval_var(var.varName)
                add_to_dict(handover2, nurse_id, interval)
            elif "break_active" in var.varName:
                nurse_id, interval = process_interval_var(var.varName)
                add_to_dict(break_shifts, nurse_id, interval)
        elif "start_interval" in var.varName:
            task_id = int(var.varName.split("[")[1].split("]")[0])
            add_task_interval(task_intervals, task_id, var.x, "start")
        elif "end_interval" in var.varName:
            task_id = int(var.varName.split("[")[1].split("]")[0])
            add_task_interval(task_intervals, task_id, var.x, "end")

    # Generate events and resources based on type
    events = []
    resources = []

    if calendar_type == "task":
        # Only include task events and resources
        task_events = generate_task_events(task_intervals, task_sheet_df)
        events = task_events  
        resources = [{"id": "tasks", "task": "All Tasks"}]
        
        # Use task names as resource IDs
        if not task_sheet_df.empty and 'Task' in task_sheet_df.columns:
            for _, row in task_sheet_df.iterrows():
                task_name = row['Task']
                resources.append({
                    "id": task_name,  # Use task name directly as ID
                    "task": task_name,
                    "parentId": "tasks"
                })

    elif calendar_type == "shift":
        # Only include nurse-related events and resources
        events.extend(generate_shift_events(nurse_shifts))
        events.extend(generate_handover_events(handover1, "H1"))
        events.extend(generate_handover_events(handover2, "H2"))
        events.extend(generate_break_events(break_shifts))
        resources.extend(generate_nurse_resources(nurse_shifts))

    else: # total calendar
        events.extend(generate_shift_events(nurse_shifts))
        events.extend(generate_handover_events(handover1, "H1"))
        events.extend(generate_handover_events(handover2, "H2"))
        events.extend(generate_break_events(break_shifts))
        events.extend(generate_task_events(task_intervals, task_sheet_df))
        
        # Add both nurse and task resources
        resources = [{"id": "tasks", "task": "All Tasks"}]
        resources.extend(generate_nurse_resources(nurse_shifts))
        
        # Use task names as resource IDs
        if not task_sheet_df.empty and 'Task' in task_sheet_df.columns:
            for _, row in task_sheet_df.iterrows():
                task_name = row['Task']
                resources.append({
                    "id": task_name,
                    "task": task_name,
                    "parentId": "tasks"
                })

    # Set final calendar options
    base_options["resources"] = resources

    # Create and return calendar with unique key per type
    calendar = sc.calendar(
        events=events,
        options=base_options,
        key=f"calendar_{calendar_type}",
        callbacks=[] 
    )

    return calendar, nurse_shifts, break_shifts, handover1, handover2

def process_interval_var(var_name):
    """Extract nurse_id and interval from variable name correctly mapping to personnel_df"""
    parts = var_name.split("[")[1].split("]")[0].split(",")
    original_id = int(parts[0])  # Original nurse ID from model
    interval = int(parts[1])
    
    # Calculate which day of week (0-6) this interval belongs to
    day = interval // 96  # Integer division to get day number
    day_interval = interval % 96  # Remainder gives interval within day
    
    # Map the nurse ID based on personnel_df length and day
    total_nurses = st.session_state.personnel_df_final.shape[0]  # Get total number of nurses
    actual_nurse = ((original_id - 1) % total_nurses) + 1  # Map to actual nurse ID
    
    # Return mapped nurse ID and interval data
    return actual_nurse, (day + 1, day_interval)

def add_to_dict(target_dict, nurse_id, interval_data):
    """Add interval data to target dictionary ensuring 7 shifts per nurse"""
    day, day_interval = interval_data
    
    # Initialize nested structures if needed
    if day not in target_dict:
        target_dict[day] = {}
    if nurse_id not in target_dict[day]:
        target_dict[day][nurse_id] = []
        
    # Add the interval to this nurse's schedule for this day
    target_dict[day][nurse_id].append(day_interval)
    target_dict[day][nurse_id].sort()

    # Count total shifts for this nurse
    nurse_total_shifts = sum(1 for d in target_dict.values() 
                           for nid, shifts in d.items() 
                           if nid == nurse_id)
    
    if nurse_total_shifts > 7:
        # Remove extra shifts if more than 7 are assigned
        excess = nurse_total_shifts - 7
        while excess > 0 and target_dict[day][nurse_id]:
            target_dict[day][nurse_id].pop()
            excess -= 1

def add_task_interval(task_intervals, task_id, interval_value, bound_type):
    """Add task interval data"""
    day = (int(interval_value) // 96) + 1
    day_interval = int(interval_value) % 96
    
    if day not in task_intervals:
        task_intervals[day] = {}
    if task_id not in task_intervals[day]:
        task_intervals[day][task_id] = {}
    task_intervals[day][task_id][bound_type] = day_interval

def get_next_monday():
    """Get the date of the upcoming Monday in YYYY-MM-DD format"""
    today = datetime.now()
    days_ahead = (0 - today.weekday()) % 7
    next_monday = today + timedelta(days=days_ahead)
    return next_monday.strftime("%Y-%m-%d")

def generate_shift_events(nurse_shifts):
    """Generate calendar events for nurse shifts across the full week"""
    events = []
    next_monday = get_next_monday()
    total_nurses = st.session_state.personnel_df_final.shape[0]
    nurse_shift_counts = {}  # Track shifts per nurse
    
    # Initialize shift counts
    for nurse_id in range(1, total_nurses + 1):
        nurse_shift_counts[nurse_id] = 0
        
    # Process each day of the week in order
    for day in range(1, 8):  # Days 1-7
        date = datetime.strptime(next_monday, "%Y-%m-%d") + timedelta(days=day-1)
        
        if day in nurse_shifts:
            for nurse_id in sorted(nurse_shifts[day].keys()):
                if nurse_shift_counts[nurse_id] >= 7:
                    continue  # Skip if nurse already has 7 shifts
                    
                intervals = sorted(nurse_shifts[day][nurse_id])
                shift_groups = []
                current_group = []
                
                for interval in intervals:
                    if not current_group or interval == current_group[-1] + 1:
                        current_group.append(interval)
                    else:
                        shift_groups.append(current_group)
                        current_group = [interval]
                if current_group:
                    shift_groups.append(current_group)
                
                # Create events for valid shifts
                for group in shift_groups:
                    if nurse_shift_counts[nurse_id] < 7:
                        start_time = f"{int(group[0]/4):02d}:{(group[0]%4)*15:02d}"
                        end_time = f"{int((group[-1]+1)/4):02d}:{((group[-1]+1)%4)*15:02d}"
                        
                        events.append({
                            "title": f"Nurse {nurse_id}",
                            "start": f"{date.strftime('%Y-%m-%d')}T{start_time}",
                            "end": f"{date.strftime('%Y-%m-%d')}T{end_time}",
                            "resourceId": nurse_id,
                            "backgroundColor": "#B8CCE4",
                            "borderColor": "#B8CCE4"
                        })
                        nurse_shift_counts[nurse_id] += 1
    
    events.sort(key=lambda x: x["start"])
    return events

def generate_handover_events(handover_shifts, handover_type):
    """Generate calendar events for handovers across the week"""
    events = []
    next_monday = get_next_monday()
    
    for day in handover_shifts:
        # Calculate the date for this day
        date = datetime.strptime(next_monday, "%Y-%m-%d") + timedelta(days=day-1)
        
        for nurse_id, intervals in handover_shifts[day].items():
            handover_groups = []
            current_group = []
            
            for interval in sorted(intervals):
                if not current_group or interval == current_group[-1] + 1:
                    current_group.append(interval)
                else:
                    handover_groups.append(current_group)
                    current_group = [interval]
            if current_group:
                handover_groups.append(current_group)
            
            for group in handover_groups:
                start_time = f"{int(group[0]/4):02d}:{(group[0]%4)*15:02d}"
                end_time = f"{int((group[-1]+1)/4):02d}:{((group[-1]+1)%4)*15:02d}"
                
                events.append({
                    "title": f"{handover_type}",
                    "start": f"{date.strftime('%Y-%m-%d')}T{start_time}",
                    "end": f"{date.strftime('%Y-%m-%d')}T{end_time}",
                    "resourceId": nurse_id,
                    "backgroundColor": "#90EE90",
                    "borderColor": "#90EE90"
                })
    
    return events

def generate_break_events(break_shifts):
    """Generate calendar events for breaks across the week"""
    events = []
    next_monday = get_next_monday()
    
    for day in break_shifts:
        # Calculate the date for this day
        date = datetime.strptime(next_monday, "%Y-%m-%d") + timedelta(days=day-1)
        
        for nurse_id, intervals in break_shifts[day].items():
            break_groups = []
            current_group = []
            
            for interval in sorted(intervals):
                if not current_group or interval == current_group[-1] + 1:
                    current_group.append(interval)
                else:
                    break_groups.append(current_group)
                    current_group = [interval]
            if current_group:
                break_groups.append(current_group)
            
            for group in break_groups:
                start_time = f"{int(group[0]/4):02d}:{(group[0]%4)*15:02d}"
                end_time = f"{int((group[-1]+1)/4):02d}:{((group[-1]+1)%4)*15:02d}"
                
                events.append({
                    "title": "Break",
                    "start": f"{date.strftime('%Y-%m-%d')}T{start_time}",
                    "end": f"{date.strftime('%Y-%m-%d')}T{end_time}",
                    "resourceId": nurse_id,
                    "backgroundColor": "#FF9999",
                    "borderColor": "#FF9999"
                })
    
    return events

def generate_task_events(task_intervals, task_sheet_df):
    events = []
    next_monday = get_next_monday()
    
    for day in task_intervals:
        date = datetime.strptime(next_monday, "%Y-%m-%d") + timedelta(days=day-1)
        
        for task_id, bounds in task_intervals[day].items():
            if 'start' in bounds and 'end' in bounds:
                start_interval = bounds['start']
                end_interval = bounds['end']
                
                start_time = f"{int(start_interval/4):02d}:{(start_interval%4)*15:02d}"
                end_time = f"{int((end_interval+1)/4):02d}:{((end_interval+1)%4)*15:02d}"
                
                task_name = f"Task {task_id}"
                if not task_sheet_df.empty and 'Task' in task_sheet_df.columns:
                    task_row = task_sheet_df[task_sheet_df.index == task_id]
                    if not task_row.empty:
                        task_name = task_row['Task'].iloc[0]
                        num_nurses = task_row['# Nurses'].iloc[0]
                        
                        event = {
                            "title": f"{task_name} ({num_nurses} nurses)",
                            "start": f"{date.strftime('%Y-%m-%d')}T{start_time}",
                            "end": f"{date.strftime('%Y-%m-%d')}T{end_time}", 
                            "backgroundColor": "#FFD700",
                            "borderColor": "#FFD700",
                            "resourceId": task_name  # Add prefix and zero-padding
                        }
                        events.append(event)
    
    # Sort events by task ID numerically
    events.sort(key=lambda x: x["start"])
    return events

def generate_nurse_resources(nurse_shifts):
    """Generate resources list for nurses"""
    resources = []
    nurse_ids = set()
    
    for day in nurse_shifts:
        nurse_ids.update(nurse_shifts[day].keys())
    
    for nurse_id in sorted(nurse_ids):
        resources.append({
            "id": nurse_id,
            "nurse_id": f"Nurse {nurse_id}"
        })
        
    return resources
