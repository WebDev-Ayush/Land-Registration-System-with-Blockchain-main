"""Check MongoDB state"""
from pymongo import MongoClient
import json

c = MongoClient("mongodb://localhost:27017")

# Revenue Dept Employees
print("=== Revenue Dept Employees ===")
emps = list(c.Revenue_Dept.Employees.find())
print(f"Count: {len(emps)}")
for e in emps:
    safe = {k: str(v)[:80] for k, v in e.items() if k != "_id"}
    print(f"  {json.dumps(safe)}")

# LandRegistry collections
print("\n=== LandRegistry Collections ===")
for col in c.LandRegistry.list_collection_names():
    count = c.LandRegistry[col].count_documents({})
    print(f"  {col}: {count} docs")

# Property_Docs
print("\n=== Property_Docs ===")
docs = list(c.LandRegistry.Property_Docs.find())
print(f"Count: {len(docs)}")
for d in docs[:3]:
    safe = {k: str(v)[:60] for k, v in d.items() if k != "_id"}
    print(f"  {json.dumps(safe)}")

# fs.files (GridFS)
print("\n=== GridFS files ===")
files = list(c.LandRegistry.fs.files.find())
print(f"Count: {len(files)}")
