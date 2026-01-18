import pymysql
from getpass import getpass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

# ------------------------------------------------------------
# OTHERS
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "",
    "user": "",
    "password": "",
    "db": "bank_app",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False
}

def money(x):
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def connect():
    return pymysql.connect(**DB_CONFIG)

# ------------------------------------------------------------
# USER CREATION
# ------------------------------------------------------------
def create_user(conn, fname, minit, lname, birthday, email, password, phone):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user (FName, Minit, LName, Birthday, Email, Password, PhoneNumber)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (fname, minit, lname, birthday, email, password, phone))
    conn.commit()
    print("User successfully created!")

# ------------------------------------------------------------
# USER/ADMIN LOGIN
# ------------------------------------------------------------
def user_login(conn):
    print("\n=== USER LOGIN ===")
    email = input("Email: ").strip()
    password = getpass("Password: ")

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user WHERE Email=%s AND Password=%s",(email, password))
        row = cur.fetchone()
        if row:
            print(f"Welcome, {row['FName']}!")
            return row
        print("Invalid email or password.")
        return None

def admin_login(conn):
    print("\n=== ADMIN LOGIN ===")
    email = input("Email: ").strip()
    password = getpass("Password: ")

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM admin WHERE Email=%s AND Password=%s", (email, password))
        row = cur.fetchone()
        if row:
            print(f"Admin logged in: {row['FName']}")
            return row
        print("Invalid admin credentials.")
        return None

# ------------------------------------------------------------
# ACCOUNT MANAGEMENT
# ------------------------------------------------------------

def create_account(conn, user_id, init_balance, admin_id, account_type):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO account (UserID, AdminID, Balance, AccountType)
            VALUES (%s, %s, %s, %s)
        """, (user_id, admin_id, init_balance, account_type))

    conn.commit()
    print("Account successfully created.")

def delete_account(conn, account_id, user_id):
    try:
        with conn.cursor() as cur:
            conn.begin()

            #check if the user inputed proper account num (that belongs to them)
            cur.execute("""
                SELECT AccountID FROM account
                WHERE AccountID=%s AND UserID=%s
            """, (account_id, user_id))
            if not cur.fetchone():
                raise Exception("You do not own this account.")

            #delete transactions
            cur.execute("""
                DELETE FROM transaction
                WHERE SourceAccountID=%s OR RecipientAccountID=%s
            """, (account_id, account_id))

            #delete autotransfers
            cur.execute("""
                DELETE FROM autotransfer
                WHERE SourceAccountID=%s OR TargetAccountID=%s
            """, (account_id, account_id))

            #delete account
            cur.execute("DELETE FROM account WHERE AccountID=%s", (account_id,))

            conn.commit()
            print("Account successfully deleted.")

    except Exception as e:
        conn.rollback()
        print("Delete failed:", e)

# ------------------------------------------------------------
# TRANSACTIONS (Deposit, Withdraw, Transfer)
# ------------------------------------------------------------
def deposit(conn, source_id, amount, desc=None):
    amount = money(amount)
    try:
        with conn.cursor() as cur:
            conn.begin()

            cur.execute("SELECT Balance FROM account WHERE AccountID=%s FOR UPDATE", (source_id,))
            row = cur.fetchone()
            if not row:
                raise Exception("Account not found.")

            new_balance = money(row['Balance']) + amount

            cur.execute("UPDATE account SET Balance=%s WHERE AccountID=%s", (new_balance, source_id))

            cur.execute("""
                INSERT INTO transaction
                (SourceAccountID, Type, Amount, Description)
                VALUES (%s, 'Deposit', %s, %s)
            """, (source_id, amount, desc))

            conn.commit()
            print("Deposit successful. New balance:", new_balance)
    except Exception as e:
        conn.rollback()
        print("Deposit failed:", e)

def withdraw(conn, source_id, amount, desc=None):
    amount = money(amount)
    try:
        with conn.cursor() as cur:
            conn.begin()

            cur.execute("SELECT Balance FROM account WHERE AccountID=%s FOR UPDATE", (source_id,))
            row = cur.fetchone()
            if not row:
                raise Exception("Account not found.")

            if money(row['Balance']) < amount:
                raise Exception("Insufficient funds.")

            new_balance = money(row['Balance']) - amount

            cur.execute("UPDATE account SET Balance=%s WHERE AccountID=%s",(new_balance, source_id))

            cur.execute("""
                INSERT INTO transaction
                (SourceAccountID, Type, Amount, Description)
                VALUES (%s, 'Withdraw', %s, %s)
            """, (source_id, amount, desc))

            conn.commit()
            print("Withdraw successful. New balance:", new_balance)
    except Exception as e:
        conn.rollback()
        print("Withdraw failed:", e)

def transfer(conn, source_id, target_id, amount, desc=None):
    amount = money(amount)
    try:
        with conn.cursor() as cur:
            conn.begin()

            a1, a2 = sorted([source_id, target_id])
            cur.execute("""
                SELECT AccountID, Balance
                FROM account
                WHERE AccountID IN (%s, %s)
                FOR UPDATE
            """, (a1, a2))
            rows = cur.fetchall()
            if len(rows) < 2:
                raise Exception("One or both accounts do not exist.")

            bal = {r['AccountID']: money(r['Balance']) for r in rows}

            if bal[source_id] < amount:
                raise Exception("Insufficient funds.")

            bal[source_id] -= amount
            bal[target_id] += amount

            cur.execute("UPDATE account SET Balance=%s WHERE AccountID=%s",(bal[source_id], source_id))
            cur.execute("UPDATE account SET Balance=%s WHERE AccountID=%s",(bal[target_id], target_id))

            cur.execute("""
                INSERT INTO transaction
                (SourceAccountID, RecipientAccountID, Type, Amount, Description)
                VALUES (%s, %s, 'Transfer', %s, %s)
            """, (source_id, target_id, amount, desc))

            conn.commit()
            print("Transfer successful!")
    except Exception as e:
        conn.rollback()
        print("Transfer failed:", e)

# ------------------------------------------------------------
# AUTOTRANSFER
# ------------------------------------------------------------
def create_autotransfer(conn, source, target, amount, frequency, date):
    amount = money(amount)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO autotransfer
            (SourceAccountID, TargetAccountID, Amount, Frequency, TransferDate)
            VALUES (%s,%s,%s,%s,%s)
        """, (source, target, amount, frequency, date))
    conn.commit()
    print("AutoTransfer successfully created.")


# ------------------------------------------------------------
# LIST
# ------------------------------------------------------------

def list_user_accounts(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM account
            WHERE UserID = %s
            ORDER BY AccountID
        """, (user_id,))
        rows = cur.fetchall()
        print_table(rows, ["AccountID", "AccountType", "Balance", "Status", "CreatedTime"])

def list_all_accounts(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.*, u.FName, u.LName
            FROM account a
            JOIN user u ON a.UserID = u.UserID
            ORDER BY AccountID
        """)
        rows = cur.fetchall()
        print_table(rows, ["AccountID", "FName", "LName", "AccountType", "Balance", "Status", "CreatedTime"])

def list_user_transactions(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM transaction
            WHERE SourceAccountID IN (
                SELECT AccountID FROM account WHERE UserID=%s
            )
            ORDER BY TransactionID DESC
        """, (user_id,))

        rows = cur.fetchall()
        print_table(rows, ["TransactionID", "SourceAccountID", "RecipientAccountID","Type", "Amount", "Description", "CreatedTime"])
       
def list_all_transactions(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM transaction
            ORDER BY TransactionID DESC
        """)
        rows = cur.fetchall()
        print_table(rows, ["TransactionID", "SourceAccountID", "RecipientAccountID","Type", "Amount", "Description", "CreatedTime"])

def list_user_autotransfers(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT at.*
            FROM autotransfer at
            JOIN account a ON at.SourceAccountID = a.AccountID
            WHERE a.UserID = %s
            ORDER BY AutoTransferID
        """, (user_id,))
        rows = cur.fetchall()
        print_table(rows, ["AutoTransferID", "SourceAccountID", "TargetAccountID","Amount", "Frequency", "TransferDate", "created_at"])

def list_all_autotransfers(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * 
            FROM autotransfer 
            ORDER BY AutoTransferID
        """)
        rows = cur.fetchall()
        print_table(rows, ["AutoTransferID", "SourceAccountID", "TargetAccountID", "Amount", "Frequency", "TransferDate", "created_at"])


# ------------------------------------------------------------
# ADMIN CONTROLS (user)
# ------------------------------------------------------------

def search_user(conn):
    print("\n=== USER SEARCH ===")
    key = input("Enter first name, last name, or email: ").strip()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM user
            WHERE FName LIKE %s
               OR LName LIKE %s
               OR Email LIKE %s
        """, (f"%{key}%", f"%{key}%", f"%{key}%"))
        
        users = cur.fetchall()

        if not users:
            print(" No users found.")
            return None

        print(f"\nFound {len(users)} user(s):\n")
        print_table(users, [
            "UserID", "FName", "LName",
            "Email", "PhoneNumber", "CreatedTime"
        ])
        try:
            user_id = int(input("\nEnter UserID to manage (0 = cancel): "))
            if user_id == 0:
                return None
            return user_id
        except:
            return None

def admin_manage_user(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("SELECT FName, LName FROM user WHERE UserID=%s", (user_id,))
        user = cur.fetchone()

    while True:
        print(f"""
===========================================================
    VIEW USER (ID: {user_id}, Name: {user['FName']} {user['LName']})
===========================================================
1) View user's accounts
2) View user's transactions
3) View user's autotransfers
0) Back
""")

        c = input("Choice: ").strip()

        if c == '0': #back
            break

        elif c == '1': 
            list_user_accounts(conn, user_id)

        elif c == '2':
            list_user_transactions(conn, user_id)

        elif c == '3':
            list_user_autotransfers(conn, user_id)

# ------------------------------------------------------------
# MENUS
# ------------------------------------------------------------
def login_menu():
    print("""
===========================
        LOGIN MENU
===========================
1) Login as User
2) Login as Admin
3) Signup as User
0) Exit
""")

def user_menu_main():
    print("""
===========================
        USER MENU
===========================
1) Create my account
2) View my accounts
3) Create my transaction
4) View my transactions
5) Create AutoTransfer
6) View my AutoTransfers
7) Delete my account
0) Logout
""")

def user_menu_transaction():
    print("""
===========================
        TRANSACTION
===========================
1) Deposit
2) Withdraw
3) Transfer
""")

def admin_menu_main():
    print("""
===========================
        ADMIN MENU
===========================
1) List all ...
2) View a user's ...
0) Logout
""")
    
def admin_menu_list():
      print("""
===========================
        List all...
===========================
1) List all accounts
2) List all transactions
3) List all autotransfers
""")  
    

def print_table(rows, headers=None):
    if not rows:
        print("(no data)")
        return

    # If no custom header order, use keys from first row
    if headers is None:
        headers = list(rows[0].keys())

    # Convert all values to strings
    str_rows = []
    for row in rows:
        str_rows.append([str(row.get(h, "")) for h in headers])

    # Compute column widths
    col_widths = []
    for i, h in enumerate(headers):
        width = max(len(h), max(len(r[i]) for r in str_rows))
        col_widths.append(width)

    # Header line
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))

    # Rows
    for r in str_rows:
        print("  ".join(r[i].ljust(col_widths[i]) for i in range(len(headers))))
 
# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    try:
        conn = connect()
    except Exception as e:
        print("DB Connection failed:", e)
        return

    while True:
        login_menu()
        choice = input("Choice: ").strip()

        # User LOGIN
        if choice == '1':
            user = user_login(conn)
            if not user:
                continue
            while True:
                user_menu_main()
                c = input("Choice: ").strip()

                if c == '0':
                    print("Successfuly Logged Out.")
                    break

                elif c == '1': #create an account
                    print("\nCreate your account:")
                    initial_bal = Decimal(input("Initial balance: ") or 0)

                    print("\nChoose type:")
                    print("1) Checking (입출금)")
                    print("2) Savings (예금)")
                    print("3) Installment Savings (적금)\n")
                    
                    type_choice = input("Choice: ")

                    if type_choice == '1': 
                        account_type = "Checking Account"
                    elif type_choice == '2': 
                        account_type = "Savings Account"
                    elif type_choice == '3':
                        account_type = "Installment Savings Account"
                    else: #default checking account
                        account_type = "Checking Account"

                    create_account(conn, user['UserID'], initial_bal, None, account_type)

                elif c == '2': #view all accounts
                    print("\n")
                    list_user_accounts(conn, user['UserID'])
                
                elif c == '3': #create transaction
                    user_menu_transaction()
                    transaction_choice = input("Choice: ")
                    if transaction_choice == '1': #deposit
                        account_id = int(input("Account ID: "))
                        amount = Decimal(input("Amount: "))
                        description = input("Description: ")
                        print("\n")
                        deposit(conn, account_id, amount, description)

                    elif transaction_choice == '2': #withdraw
                        account_id = int(input("Account ID: "))
                        amount = Decimal(input("Amount: "))
                        description = input("Description: ")
                        print("\n")
                        withdraw(conn, account_id, amount, description)

                    elif transaction_choice == '3': #transfer
                        source_id = int(input("Source Account ID: "))
                        recipient_id = int(input("Recipient Account ID: "))
                        amount = Decimal(input("Amount: "))
                        description = input("Description: ")
                        print("\n")
                        transfer(conn, source_id, recipient_id, amount, description)

                elif c == '4': #view transactions
                    list_user_transactions(conn, user['UserID'])

                elif c == '5': #create auttransfer
                    source_id = int(input("Source Account ID: "))
                    target_id = int(input("Target Account ID: "))
                    amount = Decimal(input("Amount: "))
                    frequency = input("Frequency: ")
                    transfer_date = input("Transfer date (YYYY-MM-DD HH:MM): ")
                    print("\n")
                    create_autotransfer(conn, source_id, target_id, amount, frequency, transfer_date)

                elif c == '6': #list autotransfer
                    list_user_autotransfers(conn, user['UserID'])

                elif c == '7': #delete account
                    account_id = int(input("Enter Account ID to delete: "))
                    delete_account(conn, account_id, user['UserID'])

        # Admin LOGIN
        elif choice == '2':
            admin = admin_login(conn)
            if not admin:
                continue

            while True:
                admin_menu_main()
                c = input("Choice: ").strip()

                if c == '0':
                    print("Successfuly Logged Out.")
                    break

                elif c == '1': #list all users
                    admin_menu_list()
                    list_all_choice = input("Choice: ")
                    if list_all_choice == '1':#list all accounts
                        list_all_accounts(conn)
                    elif list_all_choice == '2': #list all transactions
                        list_all_transactions(conn)
                    elif list_all_choice == '3': #list all autotransfers
                        list_all_autotransfers(conn)

                elif c == '2': #search user and manage
                    user_id = search_user(conn)
                    if user_id:
                        admin_manage_user(conn, user_id)

        # SIGNUP
        elif choice == '3':
            print("\n ========== SIGN UP ==========")
            fname = input("First name: ")
            minit = input("Middle initial (optional): ") or None
            lname = input("Last name: ")
            birthday = input("Birthday (YYYY-MM-DD): ")
            email = input("Email: ")
            password = getpass("Password: ")
            phone_number = input("Phone number (010-xxxx-xxxx): ")

            print("\n")
            create_user(conn, fname, minit, lname, birthday, email, password, phone_number)
            continue

        elif choice == '0': 
            print("Thank you for using our service!")
            break

        else:
            print("Please choose a valid option.")


if __name__ == "__main__":
    main()
