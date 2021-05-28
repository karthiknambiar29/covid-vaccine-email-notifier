import pandas as pd
from cowin_api import CoWinAPI
from datetime import datetime, timedelta
import numpy as np
from pretty_html_table import build_table
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from time import sleep

def return_state_id(state_query):
    STATE_LIST = pd.DataFrame(cowin.get_states()['states'])
    state_query_id = None
    state_names = list(STATE_LIST['state_name'].str.lower())
    state_ids = list(map(str,STATE_LIST['state_id']))
    for state_id, state_name in zip(state_ids, state_names):
        if state_query == state_name:
            state_query_id = state_id
    return state_query_id
    
def return_district_id(state_query_id, district_query):
    DISTRICT_LIST = pd.DataFrame(cowin.get_districts(state_query_id)['districts'])
    district_query_id = None
    district_names = list(DISTRICT_LIST['district_name'].str.lower())
    district_ids = list(map(str,DISTRICT_LIST['district_id']))
    for district_id, district_name in zip(district_ids, district_names):
        if district_query == district_name:
            district_query_id = district_id
    return district_query_id

cowin = CoWinAPI()

def email_query():
    FROM_EMAIL = input("Enter From Email Id : ")
    TO_EMAIL = input("Enter To Email Id : ")
    PASSWORD = input("Enter Password of From Email Id : ")
    email_info = [FROM_EMAIL, TO_EMAIL, PASSWORD]
    return email_info

def query_input():
    query = []
    FLAG = True
    while(FLAG):
        
        flag = True
        while(flag):
            state_query = input("Type State Name : ")
            state_query_id = return_state_id(state_query)
            if state_query_id is not None:
                flag=False
            else:
                print('STATE NAME NOT VALID')

        flag = True
        while(flag):
            district_query= input("Type District Name : ")
            district_query_id = return_district_id(state_query_id, district_query)
            if district_query_id is not None:
                district_query_id = int(district_query_id)
                flag=False
            else:
                print('DISTRICT NAME NOT VALID')
            
    
        center_query = input("Type Center Name : ")

        flag=True
        while(flag):
            VACCINE = input("Vaccine (Enter 'covishield' or 'covaxin'. If you want both covishield and covaxin, enter 'both') : ").lower()
            if VACCINE == 'covishield' or VACCINE == 'covaxin':
                flag = False
            if VACCINE == 'both':
                flag = False
                VACCINE = None

        flag=True
        while(flag):
            DOSE = input("DOSE NUMBER (Enter '1' or '2'. If you want the availability of both 1st and 2nd dose, enter 'both') : ")
            if DOSE == '1' or DOSE == '2':
                flag = False
            if DOSE == 'both':
                flag=False
                DOSE = None


        flag=True
        while(flag):
            AGE = input("MINIMUM AGE LIMIT (Enter '18' or '45'. If you want 18+ and 45+ availability together, enter 'both'): ")
            if AGE == '18':
                flag = False
                AGE = [18]
            if AGE == '45':
                flag = False
                AGE = [45]
            if AGE == 'both':
                flag = False
                AGE = [18, 45]

        flag = True
        while(flag):
            NUM_DAYS = input("Enter the number of days you want to search from now. (Maximum: '7') : ")
            if NUM_DAYS in ['1', '2', '3', '4', '5', '6', '7']:
                flag=False
                NUM_DAYS = int(NUM_DAYS)

        query.append([district_query_id, center_query, VACCINE, DOSE, AGE, NUM_DAYS])
        
        flag = True
        while(flag):
            another_query = input("Do you want to check availability in another center? (Y/N) : ")
            if another_query.lower()=='y':
                FLAG=True
                flag = False
            if another_query.lower()=='n':
                FLAG=False
                flag=True
                while(flag):
                    RecheckTime = input("Enter time to recheck availability in minutes. If no recheck is needed, enter '0' : ").lower()
                    try:
                        RecheckTime = int(RecheckTime)
                        flag=False
                    except ValueError:
                        flag = True
                return query, RecheckTime

email_info = email_query()
FROM_EMAIL=email_info[0]
TO_EMAIL=email_info[1]
PASSWORD = email_info[2]

queries, recheck_time = query_input()

def check_availability(queries):
    final_info = []
    for query in queries:
        [district_query_id, center_query, VACCINE, DOSE, AGE, NUM_DAYS] = query
        DATE = [(datetime.now() + timedelta(days=days)).strftime("%d-%m-%Y") for days in range(NUM_DAYS)]
        for age in AGE:
            centers = cowin.get_availability_by_district(district_query_id, DATE, age)
            centers = pd.DataFrame(centers['centers'])
            center_names = list(centers['name'].str.lower())

            for i, center_name in enumerate(center_names):
                if center_query in center_name:
                    sessions = centers.loc[i]['sessions']
                    available_slots = []
                    for session in sessions:
                        available_slots.append(', '.join(session['slots']))
                    availability_info = pd.DataFrame(sessions, index=np.arange(len(sessions)), 
                                                 columns=['date', 'available_capacity', 'min_age_limit', 'vaccine',
                                                               'available_capacity_dose1', 'available_capacity_dose2'])
                    availability_info['slots'] = available_slots
                    availability_info['centre_name'] = centers.loc[i]['name']
                    availability_info['address'] = centers.loc[i]['address']
                    for index, row in availability_info.iterrows():
                        if row['available_capacity']:
                            if DOSE is None:
                                if VACCINE is None:
                                    final_info.append(pd.DataFrame(row).T)
                                elif row['vaccine'].lower()==VACCINE:
                                    final_info.append(pd.DataFrame(row).T)
                            elif row['available_capacity_dose'+DOSE]!=0:
                                if VACCINE is None:
                                    final_info.append(pd.DataFrame(row).T)
                                elif row['vaccine'].lower()==VACCINE:
                                    final_info.append(pd.DataFrame(row).T)
    if len(final_info)!=0:
        final_info = pd.concat(final_info, axis = 0, ignore_index=True)[['centre_name', 'address', 'date', 'available_capacity', 'min_age_limit', 'vaccine', 'available_capacity_dose1', 'available_capacity_dose2', 'slots']]
        return final_info
    else:
        return None
    
def sendmail(final_result):
    output = build_table(final_result, 'blue_light', font_size='small', text_align='center')
    context = ssl.create_default_context()
    message = MIMEMultipart()
    message['Subject'] = 'Covid Vaccination Slot is available'
    message['From'] = FROM_EMAIL
    message['To'] = TO_EMAIL
    body_content = output
    message.attach(MIMEText(body_content, "html"))
    msg_body = message.as_string()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(FROM_EMAIL, PASSWORD)
        smtp.sendmail(FROM_EMAIL, TO_EMAIL, msg_body)
        smtp.quit()
    
def main():
    print("Please wait for few seconds. Checking for availability.")
    final_result = check_availability(queries)
    if final_result is not None:
        sendmail(final_result)
        print("Email Sent at {}".format(datetime.now()))
        if recheck_time:
            print("Will check availability after {} minutes.".format(recheck_time))
    else:
        print('Not Available at {}'.format(datetime.now()))
        if recheck_time:
            print("Will check availability after {} minutes.".format(recheck_time))


if __name__ == '__main__':

    if not recheck_time:
        main()
    else:
        loop_nonstop = True
        while loop_nonstop:
            main()
            try:
                print("*Print 'Ctrl+C' if you want to stop rechecking availability and sending mail now*")
                sleep(recheck_time * 60)
            except KeyboardInterrupt:
                loop_nonstop = False
