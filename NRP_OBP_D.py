import os
import re
import pandas as pd
import numpy as np
import gurobipy as gp

weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
# create intervals for each day of the week
monday_intervals = range(0, 96)
tuesday_intervals = range(96, 192)
wednesday_intervals = range(192, 288)
thursday_intervals = range(288, 384)
friday_intervals = range(384, 480)
saturday_intervals = range(480, 576) 
sunday_intervals = range(576, 672)

days = {
    'Monday': monday_intervals,
    'Tuesday': tuesday_intervals, 
    'Wednesday': wednesday_intervals,
    'Thursday': thursday_intervals,
    'Friday': friday_intervals,
    'Saturday': saturday_intervals,
    'Sunday': sunday_intervals
}

time_range = range(672)
handover_start = 26
handover_end = 654
handover_time_range = range(handover_start, handover_end)	
handover_duration = 2  # 2 intervals = 30 minutes
break_duration = 2  # 2 intervals = 30 minutes

def model_start(tasks_df, shift_df, day_salary, night_salary):
    schedule_costs = gp.Model("NurseScheduling")
    
    # Model parameters
    schedule_costs.setParam('OutputFlag', 1)
    schedule_costs.setParam('TimeLimit', 300)

    # variables for shift scheduling
    shift_scheduled = schedule_costs.addVars(shift_df.index, vtype=gp.GRB.BINARY, name=f"shift_scheduled")
    nurse_active_at_time = schedule_costs.addVars(len(shift_df.index), time_range, vtype=gp.GRB.BINARY, name=f"nurse_active")
    all_nurses_active_at_time = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name=f"nurses_scheduled")
    works_shifts = schedule_costs.addVars(len(shift_df['Nurse_ID'].unique()), vtype=gp.GRB.BINARY, name=lambda i: f"works_shifts_{i}")

    # variables for break scheduling
    break_start_time = schedule_costs.addVars(shift_df.index, vtype=gp.GRB.INTEGER, name=f"break_start_time")
    break_end_time = schedule_costs.addVars(shift_df.index, vtype=gp.GRB.INTEGER, name=f"break_end_time")
    break_active = schedule_costs.addVars(shift_df.index, time_range, vtype=gp.GRB.BINARY, name=f"break_active")

    # variables for task execution
    active_tasks = schedule_costs.addVars(tasks_df.index, time_range, vtype=gp.GRB.BINARY, name=f"active_tasks")
    nurses_needed = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name=f"nurses_needed")

    # variables for handover
    handover1_active = schedule_costs.addVars(shift_df.index, time_range, vtype=gp.GRB.BINARY, name=f"handover1_active")
    handover2_active = schedule_costs.addVars(shift_df.index, time_range, vtype=gp.GRB.BINARY, name=f"handover2_active")
    only_handover1 = schedule_costs.addVars(time_range, vtype=gp.GRB.BINARY, name="only_handover1")
    only_handover2 = schedule_costs.addVars(time_range, vtype=gp.GRB.BINARY, name="only_handover2")

    # summing variables for handover
    all_handover1_active = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name="all_active_handover1")
    all_handover2_active = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name="all_active_handover2")
    total_handover_active = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name=f"total_handover")
    handover_needed = schedule_costs.addVars(time_range, vtype=gp.GRB.INTEGER, name=f"handover_needed")

    #variable for costs
    salary_per_interval = schedule_costs.addVars(time_range, vtype=gp.GRB.CONTINUOUS, name="salary_per_interval")
    #total_salary_day = schedule_costs.addVar(len(days), vtype=gp.GRB.CONTINUOUS, name=f"total_salary_day")

    # Start time variable
    start_interval_var = schedule_costs.addVars(tasks_df.index,
        vtype=gp.GRB.INTEGER,
        name=f"start_interval_day"
    )
    
    # End time variable
    end_interval_var = schedule_costs.addVars(tasks_df.index,
        vtype=gp.GRB.INTEGER,
        name=f"end_interval_day"
    )

    # 1 shift related constraints
    for shift_id in shift_df.index:
        for t in time_range:

            # A make sure nurse is active if shift is scheduled
            schedule_costs.addConstr(
                nurse_active_at_time[shift_id, t] <= shift_scheduled[shift_id],
            )

            # B make sure nurse is inactive before start and can be active after start shift
            schedule_costs.addConstr(
                t * nurse_active_at_time[shift_id, t] >= shift_df.loc[shift_id, 'Start'] * nurse_active_at_time[shift_id, t]
            )

            # C make sure nurse is inactive after end and can be active before end shift 
            schedule_costs.addConstr(
                (shift_df.loc[shift_id, 'End'] - 1) * nurse_active_at_time[shift_id, t] >= t * nurse_active_at_time[shift_id, t]
            )

            # D ensure nurse can be scheduled for midnight crossover shifts  --> Mandatory?
            if shift_df.loc[shift_id, 'Day'] <= shift_df.loc[shift_id, 'day_end']:
                schedule_costs.addConstr(
                    nurse_active_at_time[shift_id, t] == nurse_active_at_time[shift_id, t]
                )

            # E Ensure nurses are active for their entire shift duration 
            schedule_costs.addConstr(
                gp.quicksum(nurse_active_at_time[shift_id, t] for t in range(shift_df.loc[shift_id, 'Start'], shift_df.loc[shift_id, 'End'])) == 
                (shift_df.loc[shift_id, 'End'] - shift_df.loc[shift_id, 'Start']) * shift_scheduled[shift_id]
            )
            
        # Make sure each nurse works between 4 and 5 shifts if scheduled at all
        for nurse in shift_df['Nurse_ID'].unique():
            nurse_shifts = shift_df[shift_df['Nurse_ID'] == nurse].index
            
            # Add a variable to track if nurse is used at all
            nurse_used = schedule_costs.addVar(vtype=gp.GRB.BINARY, name=f"nurse_used_{nurse}")
            
            # F Make sure binary nurse_used is zero if not scheduled
            schedule_costs.addConstr(
                nurse_used <= gp.quicksum(shift_scheduled[i] for i in nurse_shifts)
            )

            # G Make sure binary nurse_used is one if scheduled
            schedule_costs.addConstr(
                nurse_used * len(nurse_shifts) >= gp.quicksum(shift_scheduled[i] for i in nurse_shifts)
            )

            # H Make sure nurse has at least 4 shifts when scheduled
            schedule_costs.addConstr(
                gp.quicksum(shift_scheduled[i] for i in nurse_shifts) >= 4 * nurse_used
            )

            # I Make sure nurse has at most 5 shifts when scheduled
            schedule_costs.addConstr(
                gp.quicksum(shift_scheduled[i] for i in nurse_shifts) <= 5 * nurse_used
            )


    # 2 break related constraints
    for shift_id in shift_df.index:
        break_duration = 2  # 2 intervals = 30 minutes

        # make a variable that is break window start and break window end
        break_window_start = shift_df.loc[shift_id, 'Start'] + 14
        break_window_end = shift_df.loc[shift_id, 'Start'] + 21

        for t in time_range:
            # A make sure break is inactive before start window and can be active after start break
            schedule_costs.addConstr(
                t * break_active[shift_id, t] >= break_window_start * break_active[shift_id, t] * shift_scheduled[shift_id],
            )

            # B make sure break is inactive after end window and can be active before end break
            schedule_costs.addConstr(
                t * break_active[shift_id, t] <= break_window_end * break_active[shift_id, t] * shift_scheduled[shift_id],
            )

            # C break is inactive before actual break start and can be active after actual break start   
            schedule_costs.addConstr(
                t * break_active[shift_id, t] >= break_start_time[shift_id] * break_active[shift_id, t]
            )

            # D break is inactive after actual break end and can be active before actual break end
            schedule_costs.addConstr(
                t * break_active[shift_id, t] <= break_end_time[shift_id] * break_active[shift_id, t]
            )

        # E Ensure break is active for its duration
        schedule_costs.addConstr(
            gp.quicksum(break_active[shift_id, t] for t in time_range) == break_duration * shift_scheduled[shift_id],
        )

        # F Link start break and end break with duration
        schedule_costs.addConstr(
            break_end_time[shift_id] - break_start_time[shift_id] == break_duration - 1 * shift_scheduled[shift_id],
        )

        # G ensure break is only active for shifts that are scheduled
        for t in time_range:
            schedule_costs.addConstr(
                break_active[shift_id, t] <= shift_scheduled[shift_id],
            )

    
    # H calculate the total scheduled nurses at each time
    for t in time_range:
        schedule_costs.addConstr(
            all_nurses_active_at_time[t] == gp.quicksum(nurse_active_at_time[shift_id, t] for shift_id in shift_df.index)- 
            gp.quicksum(break_active[shift_id, t] for shift_id in shift_df.index),
        )

    # 3 Task related constraints
    for task_id in tasks_df.index:
        task_duration = tasks_df.loc[task_id, 'Duration (interval)']

        for t in time_range:
            # A Task must be inactive before start and can be active after start time
            schedule_costs.addConstr(
                t * active_tasks[task_id, t] >= start_interval_var[task_id] * active_tasks[task_id, t],
                name=f"active_task_start_{task_id}{t}"
            )
            
            # B Task must be inactive after end time and can be active before end time
            schedule_costs.addConstr(
                t * active_tasks[task_id, t] <= end_interval_var[task_id] * active_tasks[task_id, t],
                name=f"active_task_end_{task_id}{t}"
            )

        # C Ensure task is active for its duration
        schedule_costs.addConstr(
            gp.quicksum(active_tasks[task_id, t] for t in time_range) == task_duration,
            name=f"task_duration_{task_id}_day"
        )

        # D Link start and end times with duration
        schedule_costs.addConstr(
            end_interval_var[task_id] - start_interval_var[task_id] == task_duration - 1,
            name=f"duration_constraint_{task_id}"
        )

        # E Start Task must happen after start window
        schedule_costs.addConstr(
            start_interval_var[task_id] >= tasks_df.loc[task_id, 'Start'],
            name=f"start_time_constraint_lower_{task_id}day"
        )
        
        # F Start Task must happen before end window
        schedule_costs.addConstr(
            start_interval_var[task_id] <= tasks_df.loc[task_id, 'End'],
            name=f"start_time_constraint_upper_{task_id}"
        )

    # initialize handover missed vector which is no gurobi variable but a boolean
    handover1_happening = [False] * len(shift_df)
    handover2_happening = [False] * len(shift_df)

    
    # 4 handover related constraints
    for shift_id in shift_df.index:
        
        handover1_start_time = shift_df.loc[shift_id, 'Start']
        handover1_end_time = shift_df.loc[shift_id, 'Start'] + 1
        
        handover2_start_time = shift_df.loc[shift_id, 'End'] - 2
        handover2_end_time = shift_df.loc[shift_id, 'End'] - 1

        handover_duration = 2  # 2 intervals = 30 minutes

        # check whether handover is missed with a boolean variable
        handover1_happening[shift_id] = handover1_end_time > handover_start
        handover2_happening[shift_id] = handover2_end_time < handover_end

        for t in handover_time_range: # monday 6:00 till sunday 20:00 
            # A handover1 must be inactive before start time and can be active after start time
            schedule_costs.addConstr(
                t * handover1_active[shift_id, t] >= handover1_start_time * handover1_active[shift_id, t],
                name=f"handover1_end_{shift_id}{t}"
            )

            # B handover 1 must be inactive before start time and can be active after start time
            schedule_costs.addConstr(
                t * handover2_active[shift_id, t] >= handover2_start_time * handover2_active[shift_id, t],
                name=f"handover2_end_{shift_id}{t}"
            )
            
            # C handover 1 must be inactive after end time and can be active before end time	
            schedule_costs.addConstr(
                t * handover1_active[shift_id, t] <= handover1_end_time * handover1_active[shift_id, t],
                name=f"handover1_end_{shift_id}{t}"
            )

            # D handover 2 must be inactive after end time and can be active before end time
            schedule_costs.addConstr(
                t * handover2_active[shift_id, t] <= handover2_end_time * handover2_active[shift_id, t],
                name=f"handover2_end_{shift_id}{t}"
            )
        
        # E handover1 task is active for its duration (only for handovers in the handover range)
        schedule_costs.addConstr(
            gp.quicksum(handover1_active[shift_id, t] for t in handover_time_range) == handover_duration * shift_scheduled[shift_id] * handover1_happening[shift_id],
            name=f"handover1_duration_{shift_id}"
        )

            # F handover2 task is active for its duration (only for handovers in the handover range)
        schedule_costs.addConstr(
            gp.quicksum(handover2_active[shift_id, t] for t in handover_time_range) == handover_duration * shift_scheduled[shift_id] * handover2_happening[shift_id],
            name=f"handover2_duration_{shift_id}"
        )

        # G ensure handover1 is only active for shifts that are scheduled
        for t in handover_time_range:
            schedule_costs.addConstr(
                handover1_active[shift_id, t] <= shift_scheduled[shift_id],
            )

        # H ensure handover2 is only active for shifts that are scheduled
        for t in handover_time_range:
            schedule_costs.addConstr(
                handover2_active[shift_id, t] <= shift_scheduled[shift_id],
            )

    for t in handover_time_range:
        # A Calculate the total number of 1_handovers active at each time
        schedule_costs.addConstr(
            all_handover1_active[t] == gp.quicksum(handover1_active[shift_id, t] for shift_id in shift_df.index)
        )

        # B Calculate the total number of 2_handovers active at each time
        schedule_costs.addConstr(
            all_handover2_active[t] == gp.quicksum(handover2_active[shift_id, t] for shift_id in shift_df.index)
        )

        # C Calculate the total number of handovers active at each time
        schedule_costs.addConstr(
            total_handover_active[t] == all_handover1_active[t] + all_handover2_active[t]
        )

        # D Make sure the binary only_handover1 is 1 if total and all handover 1 are equal
        schedule_costs.addConstr(
            (1 - only_handover1[t]) <= total_handover_active[t] - all_handover1_active[t]
        )

        # C Make sure the binary only_handover1 is 0 if there are handover2 active
        M = 50  # Large number
        schedule_costs.addConstr(
            M * (1 - only_handover1[t]) >= all_handover2_active[t]
        )

        # D Make sure the binary only_handover2 is 1 if total and all handover 2 are equal
        schedule_costs.addConstr(
            (1 - only_handover2[t]) <= total_handover_active[t] - all_handover2_active[t]
        )

        # E Make sure the binary only_handover2 is 0 if there are handover1 active
        schedule_costs.addConstr(
            M * (1 - only_handover2[t]) >= all_handover1_active[t]
        )

        # F Calculate the number of extra nurses that need a handover
        schedule_costs.addConstr(
            handover_needed[t] == only_handover1[t] * all_handover1_active[t] + only_handover2[t] * all_handover2_active[t]
        )

    # 5 concluding constraints
    # A Calculate the number of nurses needed for the tasks at each time
    for t in time_range:
        schedule_costs.addConstr(
            nurses_needed[t] == gp.quicksum(active_tasks[task_id, t] * tasks_df.loc[task_id, '# Nurses'] for task_id in tasks_df.index),
            name=f"nurses_needed_{t}"
        )
    
    # B make sure there are always more nurses active than needed in total
        schedule_costs.addConstr(
            all_nurses_active_at_time[t] >= nurses_needed[t] + all_handover1_active[t] + all_handover2_active[t] + (1/3 * handover_needed[t]),
            name=f"nurses_needed_{t}"
        )

        # C ensure that the number of nurses active is at least 2 at all times
        schedule_costs.addConstr(
            all_nurses_active_at_time[t] >= 2
        )

    # D Calculate the total salary per interval
    # Night shifts (00:00-07:00)
    for t in time_range:
        if t % 96 < 28:  # First 7 hours of each day
            schedule_costs.addConstr(
                salary_per_interval[t] == gp.quicksum(nurse_active_at_time[shift_id, t] * (night_salary/4) for shift_id in shift_df.index)
            )
        # Day shifts (07:00-18:00)
        elif t % 96 < 72:  # Next 11 hours of each day
            schedule_costs.addConstr(
                salary_per_interval[t] == gp.quicksum(nurse_active_at_time[shift_id, t] * (day_salary/4) for shift_id in shift_df.index)
            )
        # Night shifts (18:00-00:00)
        else:  # Last 6 hours of each day
            schedule_costs.addConstr(
                salary_per_interval[t] == gp.quicksum(nurse_active_at_time[shift_id, t] * (night_salary/4) for shift_id in shift_df.index)
            )
    

    # E total salary per day
    monday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_monday")
    schedule_costs.addConstr(
        monday_salary == gp.quicksum(salary_per_interval[t] for t in monday_intervals)
    )

    tuesday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_tuesday") 
    schedule_costs.addConstr(
        tuesday_salary == gp.quicksum(salary_per_interval[t] for t in tuesday_intervals)
    )

    wednesday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_wednesday")
    schedule_costs.addConstr(
        wednesday_salary == gp.quicksum(salary_per_interval[t] for t in wednesday_intervals)
    )

    thursday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_thursday")
    schedule_costs.addConstr(
        thursday_salary == gp.quicksum(salary_per_interval[t] for t in thursday_intervals)
    )

    friday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_friday")
    schedule_costs.addConstr(
        friday_salary == gp.quicksum(salary_per_interval[t] for t in friday_intervals)
    )

    saturday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_saturday")
    schedule_costs.addConstr(
        saturday_salary == gp.quicksum(salary_per_interval[t] for t in saturday_intervals)
    )

    sunday_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_sunday")
    schedule_costs.addConstr(
        sunday_salary == gp.quicksum(salary_per_interval[t] for t in sunday_intervals)
    )
    
    # Add variable for total salary
    total_weekly_salary = schedule_costs.addVar(vtype=gp.GRB.CONTINUOUS, name=f"total_salary_week")
            
    # F Calculate total salary for the whole week
    schedule_costs.addConstr(
        total_weekly_salary == gp.quicksum(salary_per_interval[t] for t in time_range)
    )

    # Objective function
    schedule_costs.setObjective(total_weekly_salary, gp.GRB.MINIMIZE)

    return schedule_costs

def main(file_path, day_salary, night_salary, type_upload='only'):
    # Salary zou dan doorgetrokken moeten worden naar de model_start functie
    # Read tasks
    tasks_df = pd.read_excel(file_path, sheet_name='Tasks')

    tasks_df['Start'] = tasks_df['Start'].apply(lambda x: float(float(x.split(':')[0]) + float(x.split(':')[1])/60.0))
    tasks_df['End'] = tasks_df['End'].apply(lambda x: float(float(x.split(':')[0]) + float(x.split(':')[1])/60.0))
    tasks_df['Duration (interval)'] = tasks_df['Duration (min)'].astype(float) / 60

    tasks_df['Start'] = (tasks_df['Start'] * 4).astype(int)
    tasks_df['End'] = (tasks_df['End'] * 4).astype(int)
    tasks_df['Duration (interval)'] = (tasks_df['Duration (interval)'] * 4).astype(int)

    # Get the shift tasks
    shift_df = pd.read_excel(file_path, sheet_name='Personnel')

    if type_upload == 'only':
        for day in weekdays:
            shift_df[f'{day} Start'] = shift_df[f'{day} Start'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else x)
            shift_df[f'{day} End'] = shift_df[f'{day} End'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else x)


    # Create mapping for days to numbers
    day_mapping = {day: i+1 for i, day in enumerate(weekdays)}

    # Create new dataframe to store transformed data
    new_shift_df = pd.DataFrame(columns=['Nurse_ID', 'Day', 'Start', 'End'])

    # For each day
    for day in weekdays:
        # Extract relevant columns for this day
        day_data = shift_df[[
            'Nurse_ID',
            f'{day} Start',
            f'{day} End'
        ]].copy()
        
        # Rename columns
        day_data.columns = ['Nurse_ID', 'Start', 'End']
        
        # Add day number
        day_data['Day'] = day_mapping[day]
        
        # Append to new dataframe
        new_shift_df = pd.concat([new_shift_df, day_data], ignore_index=False)

    shift_df = new_shift_df

    # Convert time strings to float values like in tasks_df
    shift_df['Start'] = shift_df['Start'].apply(lambda x: float(float(x.split(':')[0]) + float(x.split(':')[1])/60.0) if isinstance(x, str) else float(x))
    shift_df['End'] = shift_df['End'].apply(lambda x: float(float(x.split(':')[0]) + float(x.split(':')[1])/60.0) if isinstance(x, str) else float(x))

    # Convert to 15-minute intervals (multiply by 4)
    shift_df['Start'] = (shift_df['Start'] * 4).astype(int)
    shift_df['End'] = (shift_df['End'] * 4).astype(int)

    # convert when shift_df['End'] == 0 to 96
    shift_df['End'] = shift_df['End'].apply(lambda x: 96 if x == 0 else x)

     # a whole week has 672 intervals (96 intervals per day) make sure that the tasks are scheduled in the right interval
    shift_df['Start'] = shift_df['Start'] + (shift_df['Day'] - 1) * 96
    shift_df['End'] = shift_df['End'] + (shift_df['Day'] - 1) * 96

    # Add day_end column
    shift_df['day_end'] = shift_df['Day']

    # make sure that when a tasks start before 00:00 and finishes after 00:00 the next day that the task is scheduled in the right interval
    midnight_crossover_shift = (shift_df['Start'] > shift_df['End']) & (shift_df['Start'] != shift_df['End'])
    shift_df.loc[midnight_crossover_shift, 'day_end'] += 1
    shift_df.loc[midnight_crossover_shift, 'End'] += 96

    # convert when active_task['End'] == 0 to 96
    tasks_df['End'] = tasks_df['End'].apply(lambda x: 96 if x == 0 else x)

    # a whole week has 672 intervals (96 intervals per day) make sure  shift_df.loc[week_crossover_shift, 'Start'] = 0 that the tasks are scheduled in the right interval
    tasks_df['Start'] = tasks_df['Start'] + (tasks_df['Day'] - 1) * 96
    tasks_df['End'] = tasks_df['End'] + (tasks_df['Day'] - 1) * 96 

    # Add day_end column
    tasks_df['day_end'] = tasks_df['Day']

    # Reset index to make it continuous
    shift_df = shift_df.reset_index(drop=True)

    # print(shift_df[shift_df['Nurse_ID'] == 10])

    # Create and solve model
    model = model_start(tasks_df, shift_df, day_salary, night_salary)
    model.optimize()
    #summary 
    # # print indices of all shift_scheduled items that are 1
    # scheduled_shifts = []
    # for v in model.getVars():
    #     if 'shift_scheduled' in v.varName and v.x == 1:
    #         # Extract index number from varName using regex
    #         idx = int(re.findall(r'shift_scheduled\[(\d+)\]', v.varName)[0])
    #         scheduled_shifts.append(idx)
    # print("Indices of scheduled shifts:", scheduled_shifts)

    # # print the Nurs_ID of the scheduled shifts
    # nurses_scheduled = []
    # for idx in scheduled_shifts:
    #     nurses_scheduled.append(shift_df.loc[idx, 'Nurse_ID'])
    # # print("Nurse_ID of scheduled shifts:", nurses_scheduled)

    # # Print unique nurse IDs
    # unique_nurses = sorted(list(set(nurses_scheduled)))
    # print("\nUnique Nurse IDs scheduled:")
    # print(unique_nurses)
    # print(f"Number of nurses scheduled: {len(unique_nurses)}")
    
    # # Print scheduled shifts for each nurse
    # print("\nDetailed schedule per nurse:")
    # for nurse in shift_df['Nurse_ID'].unique():
    #     nurse_shifts = shift_df[shift_df['Nurse_ID'] == nurse].index
    #     scheduled_shifts = []
    #     for shift_id in nurse_shifts:
    #         if model.getVarByName(f'shift_scheduled[{shift_id}]').X == 1:
    #             day = weekdays[shift_df.loc[shift_id, 'Day']-1]
    #             start_time = f"{int(shift_df.loc[shift_id, 'Start']%96/4):02d}:{int((shift_df.loc[shift_id, 'Start']%96%4)*15):02d}"
    #             end_time = f"{int(shift_df.loc[shift_id, 'End']%96/4):02d}:{int((shift_df.loc[shift_id, 'End']%96%4)*15):02d}"
    #             scheduled_shifts.append(f"{day} {start_time}-{end_time}")
    #     if scheduled_shifts:  # Only print if nurse has scheduled shifts
    #         print(f"\nNurse {nurse} shifts:")
    #         for shift in scheduled_shifts:
    #             print(f"  {shift}")
    
    # #print the total salary per day
    # print(f"\nTotal salary per day:")
    # print(f"Monday: {model.getVarByName('total_salary_monday').X}")
    # print(f"Tuesday: {model.getVarByName('total_salary_tuesday').X}")
    # print(f"Wednesday: {model.getVarByName('total_salary_wednesday').X}")
    # print(f"Thursday: {model.getVarByName('total_salary_thursday').X}")
    # print(f"Friday: {model.getVarByName('total_salary_friday').X}")
    # print(f"Saturday: {model.getVarByName('total_salary_saturday').X}")
    # print(f"Sunday: {model.getVarByName('total_salary_sunday').X}")
        
    # # Print results
    # if os.path.exists('results.txt'):
    #     os.remove('results.txt')

    # with open('results.txt', 'w') as f:
    #     for v in model.getVars():
    #         f.write(f"{v.varName}: {v.X}\n")
    # print(f"Results written to results.txt")
    # print(f"\nObj: {model.objVal}")

    # model.computeIIS()
    # model.write("infeasible_model.ilp")
    
    return model

# file_path = "Hospital_Data_ext.xlsx"
# day_wage = 15
# night_wage = 20
# main(file_path, day_wage, night_wage)