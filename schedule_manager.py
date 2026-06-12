import os
from supabase import create_client, Client
from logger_config import logger
from dotenv import load_dotenv

load_dotenv()

def get_dcm_schedule(dcm_type: str = "Exterior"):
    """
    Read schedule from Supabase automation_settings table.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        logger.error("Supabase credentials missing for schedule manager.")
        return None

    try:
        clean_url = url.replace("/rest/v1/", "").strip()
        if clean_url.endswith("/"):
            clean_url = clean_url[:-1]
            
        client: Client = create_client(clean_url, key)
        
        response = client.table("automation_settings").select("*").eq("dcm_type", dcm_type).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            logger.warning(f"No schedule found for DCM Type: {dcm_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching schedule from Supabase: {str(e)}")
        return None
