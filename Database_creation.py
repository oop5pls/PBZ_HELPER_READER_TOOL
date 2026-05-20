import pandas as pd
import numpy as np
import psycopg2

#in case you do want a database you are to fill out these credentials with your own postgreSQL database credentials
#and the app will create the table if it doesn't exist and insert the data into it

def create_database():
    try:
        conn=psycopg2.connect(
            host='your_host',
            database='your_statements',
            user='your_postgres',
            password='your_password'
        )
        cursor=conn.cursor()

        create_table_query='''
        CREATE TABLE IF NOT EXISTS bankingstatement(
        transaction_id INTEGER,
        date DATE,
        transaction_type TEXT,
        transaction_description TEXT,
        amount NUMERIC,
        currency TEXT,
        expense_type TEXT
        )
        '''
        cursor.execute(create_table_query)
        conn.commit()

        cursor.close()
        conn.close()
        print("Database and table created successfully (if they didn't already exist)")
    except Exception as e:
        print("Database creation skipped",e)