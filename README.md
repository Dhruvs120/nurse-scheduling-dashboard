# Nurse Rostering Dashboard

A Streamlit-based dashboard to generate and view nurse schedules with cost analysis as part of an Assignment for the Course "Project Optimization of Business Processes" at the Vrije Universiteit Amsterdam.

## Project Structure
- **Welcome.py**  
  Main entry point for the Streamlit app.  
- **pages/1_Submit.py**  
  For uploading an Excel file, adding manual shifts, editing rates, and generating schedules.  
- **pages/2_Output.py**  
  Displays the weekly schedule with calendar views and download options.  
- **functions.py**  
  Provides helper functions to handle schedule generation.  
- **NRP_OBP_D.py**  
  Main logic for building and solving the nurse rostering model using the Gurobi software.  
- **Hospital_Data_template.xlsx**  
  Template for input schedule data.

## Installation
1. Ensure that you have a Gurobi License capable of executing large scale problems.
2. Install the required Python dependencies (e.g., `pip install -r requirements.txt`). The version of the Gurobi package should be adjusted to the version on the license.

## Usage
1. Launch the app:
   ```bash
   streamlit run Welcome.py
2. Navigate to the *Submit* page.
3. Determine whether manual additions of shifts should be required, if so, navigate to the Manual entry.
4. Use the input template provided on the dashboard or in the folder to fill in the shifts and tasks over the span of a week.
5. Make manual additions (if applicable), press the generate schedule button start generating your schedule.
6. Let the model run, after getting the notification move to the *Output* page.
7. View the results.

## Credits
- Tijmen Tans
- Dhruv Singh
- Stijn Smoes
- Joris Weenink
- VUMC for the Problem Definition