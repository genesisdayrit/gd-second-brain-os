"""
Common folder definitions for the vault organizer.
"""

# Common folders for manual selection
COMMON_FOLDERS = [
    ("06_Notes+Ideas", "Fleeting notes and ideas (~1,900+ files)"),
    ("03_Writing/_Thoughts+Sketches", "Quick thoughts and sketches"),
    ("05_Knowledge-Hub", "Knowledge repository - articles, papers, research (~5,300+ files)"),
    ("14_CRM/_People", "Individual contact notes and relationships"),
    ("14_CRM/_Deals", "Deals, opportunities, transactions"),
    ("14_CRM/_Companies+Groups+Teams", "Organizations, companies, groups, teams"),
    ("07_Experiences+Events+Meetings+Sessions", "Events, meetings, hangouts, travel (~428 files)"),
    ("12_Products+Consumption+Things", "Apps, tools, services, media consumption"),
    ("13_Places", "Cities, restaurants, venues, travel destinations (~115 files)"),
]


def get_common_folders():
    """
    Get the list of common folders for manual selection.
    Returns list of tuples: (folder_path, description)
    """
    return COMMON_FOLDERS
