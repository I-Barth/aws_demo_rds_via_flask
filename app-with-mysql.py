import os
import time
import subprocess

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


DB_IDENTIFIER = "clarusway"
AWS_REGION = "us-east-1"
POLL_INTERVAL = 10 #seconds
RDS_HOST = None

while not RDS_HOST:
    print(f"INFO: Polling AWS CLI for endpoint of DB: {DB_IDENTIFIER}...")
    # Construct the AWS CLI command
    command = [
        'aws', 'rds', 'describe-db-instances',
        '--db-instance-identifier', DB_IDENTIFIER,
        '--query', 'DBInstances[0].Endpoint.Address',
        '--region', AWS_REGION,
        '--output', 'text'
    ]

    try:
        # Execute the command (2>/dev/null suppresses stderr for clean output)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        endpoint = result.stdout.strip()
        
        # Check for success: return code is 0, endpoint is a non-empty string, and not "None"
        if result.returncode == 0 and endpoint and endpoint != "None" and "Error" not in endpoint:
            RDS_HOST = endpoint
            print(f"SUCCESS: RDS Endpoint retrieved: {RDS_HOST}")
            break
        else:
            print(f"INFO: Endpoint not yet resolved or DB not fully available. Retrying in {POLL_INTERVAL}s...")
            # print(f"DEBUG: CLI Output: {endpoint}, Return Code: {result.returncode}")
            time.sleep(POLL_INTERVAL)
            
    except FileNotFoundError:
        print("FATAL ERROR: AWS CLI command not found. Ensure 'aws' is installed and in PATH.")
        # If AWS CLI is missing, we must exit or wait for manual intervention
        time.sleep(60) 
    except Exception as e:
        print(f"An unexpected error occurred during polling: {e}")
        time.sleep(POLL_INTERVAL)    

app = Flask(__name__)

# Credentials and Database Name
DB_USER = "admin"
DB_PASS = "Clarusway_1"
DB_NAME = "clarusway"
DB_PORT = 3306

# Dynamic Configuration: Build the URI using the retrieved RDS_HOST
# We use mysql+pymysql as is common for SQLAlchemy with MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{RDS_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create an SQLAlchemy instance which will read the SQLAlchemy options of "app".
# SQLAlchemy provides a high-level abstraction layer and integration with Flask,
#    handling the tedious details of connection pooling, session lifecycle, 
#    and mapping database tables to Python objects.
#    It is a ORM Mapper and allows db interaction via objects (e.g. User.query.filter_by(name='Alice').all())
#    It is database agnostic and allows switching the underlying database with minimal changes to the code.
# It prepares its engine which manages the connections.
#    However, the connection is lazy and will be established only when the first query/operation is called.
#    Apart from managing connections, it provides access to the DB-Session and handles their life-cycle
#    It is the base class which handles any DB manipulations.
db = SQLAlchemy(app)

# app_context: Flask needs to push its context onto an internal stack for it to be active.
#              db does not store the session directly - db.session is a proxy that accesses the session stored
#                  in the app_context.
#              When the app_context is not active, Flask does not have a currently active app and db.session will be empty.
with app.app_context():
    drop_table = text('DROP TABLE IF EXISTS users;')
    users_table = text(""" 
    CREATE TABLE users(
    username VARCHAR(255) NOT NULL PRIMARY KEY,
    email VARCHAR(255));
    """)
    data = text("""
    INSERT INTO users
    VALUES
        ("dora", "dora@amazon.com"),
        ("cansın", "cansın@google.com"),
        ("sencer", "sencer@bmw.com"),
        ("uras", "uras@mercedes.com"),
	    ("ares", "ares@porsche.com");
        """)
    db.session.execute(drop_table)
    db.session.execute(users_table)
    db.session.execute(data)
    db.session.commit()

def find_emails(keyword):
    with app.app_context():
        query = text(f"""
        SELECT * FROM users WHERE username like '%{keyword}%';
        """)
        result = db.session.execute(query)
        user_emails = [(row[0], row[1]) for row in result]
        if not any(user_emails):
            user_emails = [("Not Found", "Not Found")]
        return user_emails

def insert_email(name,email):
    if len(name) == 0 or len(email) == 0:
        return 'Username or email cannot be empty!!'
    
    with app.app_context():
        query = text(f"""
        SELECT * FROM users WHERE username like '{name}'
        """)
        result = db.session.execute(query)

        if not any(result):
            insert = text(f"""
            INSERT INTO users
            VALUES ('{name}', '{email}');
            """)
            result = db.session.execute(insert)
            db.session.commit()
            return text(f"User {name} and {email} have been added successfully")
        return text(f"User {name} already exist")


@app.route('/', methods=['GET', 'POST'])
def emails():
    if request.method == 'POST':
        user_app_name = request.form['user_keyword']
        user_emails = find_emails(user_app_name)
        return render_template('emails.html', name_emails=user_emails, keyword=user_app_name, show_result=True)
    return render_template('emails.html', show_result=False)
        

@app.route('/add', methods=['GET', 'POST'])
def add_email():
    if request.method == 'POST':
        user_app_name = request.form['username']
        user_app_email = request.form['useremail']
        result_app = insert_email(user_app_name, user_app_email)
        return render_template('add-email.html', result_html=result_app, show_result=True)
    return render_template('add-email.html', show_result=False)


# - Add a statement to run the Flask application which can be reached from any host on port 80.
if __name__=='__main__':
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=8080)

# https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/