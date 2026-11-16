import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Calling Leads"

# Sample headers
ws.append(["Phone Number", "Customer Name", "City", "Notes"])

# Sample test records
sample_data = [
    ["+919980113561", "Rahul Sharma", "Bangalore", "Interested in Enterprise Plan"],
    ["+919876543210", "Priya Verma", "Mumbai", "Follow-up customer"],
    ["+919123456789", "Amit Patel", "Delhi", "New lead"],
    ["+919811223344", "Sneha Rao", "Hyderabad", "Callback requested"]
]

for row in sample_data:
    ws.append(row)

wb.save("sample_numbers_30k_template.xlsx")
print("Saved sample_numbers_30k_template.xlsx successfully!")
