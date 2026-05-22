## CSE6334 Assignment 1 Group 35
---
## How to run?
1. On Windows Server 2022 virtual machine, search "Windows Defender Firewall with Advanced Security" on the search bar, create a new rule.
2. In the new rule, select Port, then select TCP & Specific Local Ports, fill in 1433. This is your SSMS default port.
3. Next, Allow the connection, rule apply for all, name it as "Flask".
4. In your SSMS, Login as administrator, go to MYSERVER -> Databases and create database called "DataSec", then go back and click MYSERVER -> Security -> Logins and create a new login.
5. Name your new login as "flask", select SQL authentication and set your password as "Pa$$w0rd". Uncheck "Specify Old Password" & "Encorce password policy", then select your default database as "DataSec". 
6. Next, do not exit from create login, instead go to User Mapping tab. Map "flask" into DataSec, and grant role into "db_datareader", "db_datawriter", "db_ddladmin" and "db_owner".
7. Go to Status tab, grant permission to the database engine and enable login for this user.
8. Go back to the DataSec database you just created, right click into it and click properties, select Permissions page, browse "flask" and grant permission on "Connect". 
9. On your Virtualbox Manager, select your Win Server 2022 vm, go to settings, select network and check whichever has NAT attached. Once found, click Advanced, then Port Forwarding. Add a rule named "Flask", set TCP as protocol, put your ip as 127.0.0.1 and port as 1433 then click ok.
10. On your local machine, open Command Prompt and redirect the directory into whatever this directory is located, do "pip install -r requirements.txt".
11. Once installed, you can test your connection by running "test_conn.py". If it works, you may launch the python app.
12. For adding DATABASE USER, open both SQLQuarry file and execute them. then restart SSMS. 
___
### NOTE OF RUNNING ODBC DRIVERS
If you are unsure which version of odbc driver you're running try this.
1. Search ODBC on Windows Search Bar.
2. Click ODBC data sources.
3. On ODBC Data sources window, click drivers, and now you will see your ODBC driver version.

If your ODBC driver is 18, change app.py line 23 that writes f"DRIVER={{ODBC Driver XX for SQL Server}};", and test_conn.py line 9 that contains driver = "{ODBC Driver XX for SQL Server}".
___
### MKCERT INSTALL TUTORIAL.
1. Launch Powershell as Admin. 
2. Type "choco install mkcert". If finished, type "mkcert -install". (You can uninstall it by typing "mkcert -uninstall" on terminal).
3. Close powershell, go to the terminal where your run the python app.py
4. Type "mkcert localhost 127.0.0.1", to generate 2 certificate files.
5. Rename them into "localhost.pem", and "localhost-key.pem".
6. Try running the program, if you cant load into the webpage please wait for a little while. 
___

## Updates

23/4/2026 - Created the repository, Initialized database, and slightly finished home.html, homestyle.css and home()

8/5/2026 - Added Authentication & Authorization functions with hashed password, performed gray box testing on these modules.

14/5/2026 - Added admin page, and better authentication module. **_Contributed by ZBao10_**

14/5/2026 - Added HTTPS using mkcert, for security feature.

19/5/2026 - Added audit logs in admin page. 
          - Added Admin Approvals Board for deleting and promoting a user. 
          - Added Freeze account feature when login attempts are more than 5 **_Contributed by ZBao10_**

22/5/2026 - Added 2 SQLQuarry file for adding SQLDATABASE USER, (Admin and User) **_Contributed by ZBao10_**



