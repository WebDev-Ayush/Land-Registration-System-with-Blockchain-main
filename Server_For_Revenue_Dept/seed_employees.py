"""
Seed Revenue Department employees for demo/testing.
Run this once to set up employees that can log in to the Revenue Dept portal.
"""
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

client = MongoClient("mongodb://localhost:27017")
db = client.Revenue_Dept
employees = db.Employees

# Ganache accounts (0-indexed):
# 0: 0x90F8bf... (deployer/admin)
# 1: 0xFFcf8F... (employee 1)
# 2: 0x22d491... (employee 2)
# 3: 0xE11BA2... (employee 3)

EMPLOYEES = [
    {
        "employeeId": "0xffcf8fdee72ac11b5c542428b35eef5769c409f0",
        "password": generate_password_hash("password123", method="pbkdf2:sha256"),
        "fname": "Rajesh",
        "lname": "Kumar",
        "revenueDeptId": "101",
    },
    {
        "employeeId": "0x22d491bde2303f2f43325b2108d26f1eaba1e32b",
        "password": generate_password_hash("password123", method="pbkdf2:sha256"),
        "fname": "Priya",
        "lname": "Sharma",
        "revenueDeptId": "102",
    },
    {
        "employeeId": "0xe11ba2b4d45eaed5996cd0823791e0c93114882d",
        "password": generate_password_hash("password123", method="pbkdf2:sha256"),
        "fname": "Amit",
        "lname": "Singh",
        "revenueDeptId": "103",
    },
]

added = 0
for emp in EMPLOYEES:
    existing = employees.find_one({"employeeId": emp["employeeId"]})
    if existing:
        print(f"  Already exists: {emp['fname']} {emp['lname']} ({emp['employeeId'][:10]}...)")
    else:
        employees.insert_one(emp)
        added += 1
        print(f"  Added: {emp['fname']} {emp['lname']} ({emp['employeeId'][:10]}...) | Dept: {emp['revenueDeptId']} | Pass: password123")

print(f"\nDone. {added} new employees added.")
print(f"Total employees: {employees.count_documents({'employeeId': {'$exists': True}})}")
print(f"\nLogin credentials for Revenue Dept (http://localhost:5001):")
print(f"  1. Connect MetaMask with Ganache Account [1] -> password: password123")
print(f"  2. Connect MetaMask with Ganache Account [2] -> password: password123")
print(f"  3. Connect MetaMask with Ganache Account [3] -> password: password123")
print(f"\nAdmin login (http://localhost:5001/admin):")
print(f"  Address: 0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1")
print(f"  Password: 12345678")
