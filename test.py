from dotenv import load_dotenv
import os

load_dotenv()

print("MSSQL_HOST:", os.getenv("MSSQL_HOST"))
print("MSSQL_USER:", os.getenv("MSSQL_USER"))
print("MSSQL_DATABASE:", os.getenv("MSSQL_DATABASE"))
print("GOOGLE_API_KEY:", "SET" if os.getenv("GOOGLE_API_KEY") else "NOT SET")