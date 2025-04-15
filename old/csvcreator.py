import pandas as pd

# The data from india-top-medicines.txt is in CSV format
# Read it and save it as medicines.csv in the correct format
def create_medicines_database():
    # Define the data structure
    columns = ['Medicine Name', 'Generic Name', 'Physical Description', 
               'Common Brand Names', 'Standard Dosage Forms', 'Typical Usage']
    
    # Read the data from the text file
    df = pd.read_csv('medicines-dataset.md')
    
    # Save it as medicines.csv
    df.to_csv('medicines.csv', index=False)
    print("Created medicines.csv successfully!")

if __name__ == "__main__":
    create_medicines_database()