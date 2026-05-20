import psycopg2
import datetime
import pandas as pd
from types_of_expenses_dictionary import CATEGORY_RULES,CATEGORY_RULES_ASC


#the database is specifically for storing the banking statement data
#considering the data is sensitive for every user, the database should be local and not on a server, to avoid security issues
#this could be changed in the future both if i ever launch this as a product, and if i want to add a feature for users to share their data with each other (for example, to share budgets or something like that)
#the database should be a simple relational database, with a single table for the banking statement data, and possibly some additional tables for storing user preferences or other metadata in the future
#for now the insert into database functions in the app.py file will be commented out
#if the user wants to use the database, they can uncomment the lines and fill in the connection details in the get_db_connection function with their own postgreSQL database credentials, and the app will create the table if it doesn't exist and insert the data into it

#load factor of the database
alpha=0.6

def get_db_connection():
    try:
        conn=psycopg2.connect(
            host='your_host',
            database='your_statements',
            user='your_postgres',
            password='your_password',
            port=0
        )
        return conn
    except Exception as e:
        print("Error connecting to database:", e)
        return None

def get_database_rowcount(cur,conn) -> int:
    if conn is None:
        return 0
    
    try:
        # This is the SQL command that actually asks the DB for the count
        cur.execute("SELECT COUNT(*) FROM bankingstatement;")
        
        # fetchone() returns a tuple like (2320,)
        result = cur.fetchone()
    
        return result[0] if result else 0
    except Exception as e:
        print("Error getting rowcount from DB:", e)
        return 0

#returns number of rows inserted
def insert_into_db(df)->tuple[int, pd.DataFrame]:
    """Insert rows from a DataFrame into bankingstatement using bulk insert.
    Returns number of rows attempted/affected (best-effort).
    """
    conn = get_db_connection()
    if conn is None:
        print("No database connection, skipping DB insertion and categorization will be done without hashing.")
        #if there is no database we still want the categorized dataframe for graphing
        #t0=datetime.datetime.now()
        df=categorize_transaction(df)
        #print(f"Categorization completed in {(datetime.datetime.now()-t0).total_seconds():.2f}s")


        return 0,df

    cur = conn.cursor()
    # Build list of tuples in the expected order
    db_rowcount = get_database_rowcount(cur, conn)


    #data we need for graphs, transaction_id isnt importnat
    t0=datetime.datetime.now()
    df=categorize_transaction(df)
    print(f"Categorization completed in {(datetime.datetime.now()-t0).total_seconds():.2f}s")
     #insert a column for the transaction ID at the beginning of the dataframe



    #INSERT-------------------------------------------------------------
    df_insert=df.copy()
    df_insert.insert(0,'TRANS_ID',0)
    #HASHING-------------------------------------------------------------
    get_last_date='''SELECT MAX(date) FROM bankingstatement;'''
    cur.execute(get_last_date)
    result=cur.fetchone()[0]
    last_date=result if result is not None else None
    if last_date is not None:
        df_insert.drop(df[df['DATUM']<=last_date].index,inplace=True)
        #removing dates that are already in the database
        #since we PBZ doesnt have an identifier for transactions
        #we have to rely on the date
    cur_date=datetime.datetime.now().date()
    df_insert.drop(df_insert[df_insert['DATUM']>=cur_date].index,inplace=True)
    #removing todays date and possible future dates

    if db_rowcount==0: #if there are no rows in the database we can just add the transaction IDs without worrying about collisions
        df_insert=add_transaction_id(df_insert,df_insert.shape[0])
    else:
        df_insert=add_transaction_id(df_insert,db_rowcount)
    #----------------------------------------------------------------------

    rows = list(df_insert.itertuples(index=False, name=None))
    print(f"Prepared {len(rows)} rows for insertion into DB.")

    inserted = 0

    if len(rows) == 0:
        print("No new rows to insert after filtering by date.")
        return 0, df
    else:
        data = [row + (row[1], row[4], row[3],db_rowcount) for row in rows]
        print("Sample data to insert:\n")
        print(data[0])
        print("...\n")
        insert_sql =  '''
        INSERT INTO bankingstatement (transaction_id, date, transaction_type, transaction_description, amount, currency,expense_type)
        SELECT %s, %s, %s, %s, %s, %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM bankingstatement bk
            WHERE bk.date = %s::DATE AND bk.amount = %s AND bk.transaction_description = %s
            AND bk.transaction_id = %s
        );
        '''
        try:
            cur.executemany(insert_sql, data)
            conn.commit()
            # psycopg2's rowcount may be -1 or driver dependent; return len(data) as attempted
            inserted = get_database_rowcount(cur,conn) - db_rowcount

        except Exception as e:
            print("Error while updating database:", e)
    cur.close()
    conn.close()

    return inserted,df
        

#Categorization functions

def categorize_desc(description: str) -> str:
    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if keyword in description:
                return category
    return "OTHER"

def categorize_transaction(df: pd.DataFrame) -> pd.DataFrame:
    df.insert(5,'EXPENSE TYPE',str(None))
    old_desc=str(None)

    #group similar values together
    df=df.sort_values(by=['OPIS PLAĆANJA']).reset_index(drop=True)

    #categorise
    for index,row in df.iterrows():
        raw_description=row['OPIS PLAĆANJA']
        description = raw_description.upper().removeprefix("POS ").removeprefix("ONLINE ").removeprefix("PBZ ").strip()
        if index==0:
            old_desc=description
            category=categorize_desc(description)
            df.at[index,'EXPENSE TYPE']=category
        elif(description!=old_desc):
            old_desc=description
            category=categorize_desc(description)
            df.at[index,'EXPENSE TYPE']=category
        else:
            df.at[index,'EXPENSE TYPE']=df.at[index-1,'EXPENSE TYPE']
    
    return df


#Hashing functions for generating transaction IDs based on the date and description of the transaction

def my_hash2(s: str,db_size:int) ->int:
    #the size of the database thus far is the amount of keys
    #so we must calculate the length of our hash table based on the load factor and current size of the database
    table_size=int(db_size/alpha)+1
    a=abs(hash(s))
    return a%table_size
    
def my_hash1(date:datetime.date,db_size:int)->int:
    table_size=int(db_size/alpha)+1
    a=abs(hash(date.strftime("%Y%m%d")))
    return (1+a)%(table_size-1)

def add_transaction_id(df: pd.DataFrame,db_rowcount:int) -> pd.DataFrame:
    size_of_hash=int(db_rowcount/alpha)+1
    for index,row in df.iterrows():
        for i in range(size_of_hash):
            hash=(my_hash1(row['DATUM'],db_rowcount)+my_hash2(row['OPIS PLAĆANJA'],db_rowcount)+i)%(size_of_hash)
            if hash in df['TRANS_ID'].values:
                continue
            else:
                df.at[index,'TRANS_ID']=hash
                break
    return df




