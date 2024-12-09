import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from ALM_APP.models import Ldn_Product_Master

class Command(BaseCommand):
    help = 'Imports product master data from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='The path to the CSV file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        
        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    # Parse date
                    fic_mis_date = datetime.strptime(row['FIC_MIS_DATE'], '%m/%d/%Y').date()
                    
                    # Create a new record and save it to the database
                    Ldn_Product_Master.objects.create(
                        fic_mis_date=fic_mis_date,
                        v_common_coa_code=row['V_COMMON_COA_CODE'],
                        v_prod_code=row['V_PROD_CODE'],
                        v_prod_name=row['V_PROD_NAME'],
                        v_prod_type=row['V_PROD_TYPE'],
                        v_prod_type_desc=row['V_PROD_TYPE_DESC'],
                        # v_accrual_basis_code=row['V_ACCRUAL_BASIS_CODE'] if row['V_ACCRUAL_BASIS_CODE'] else None,
                        # v_rollup_signage_code=row['V_ROLLUP_SIGNAGE_CODE'],
                        v_balance_sheet_category=row['V_BALANCE_SHEET_CATEGORY'] if row['V_BALANCE_SHEET_CATEGORY'] else None,
                        v_balance_sheet_category_desc=row['V_BALANCE_SHEET_CATEGORY_DESC'] if row['V_BALANCE_SHEET_CATEGORY_DESC'] else None,
                        # v_prod_group=row['V_PROD_GROUP'] if row['V_PROD_GROUP'] else None,
                        v_prod_group_desc=row['V_PROD_GROUP_DESC']
                    )
                
                self.stdout.write(self.style.SUCCESS('Data imported successfully!'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"File {file_path} not found."))
        except csv.Error as e:
            self.stdout.write(self.style.ERROR(f"CSV error: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
