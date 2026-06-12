from supabase_writer import SupabaseWriter

writer = SupabaseWriter()

writer.append_candidate({
    "name": "Test User",
    "classification": "FIT",
    "reasoning": "Testing Supabase connection",
    "current_position": "Facade Manager",
    "location": "London",
    "cv_id": "TEST001",
    "cv_link": "https://example.com/cv.pdf",
    "platform_name": "CV Library",
    "dcm_type": "Exterior"
})