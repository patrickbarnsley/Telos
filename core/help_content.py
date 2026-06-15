HELP_CONTENT = {
    "Profile": {
        "title": "Setting up your Profile",
        "steps": [
            "Upload your resume — PDF or Word (.docx) both work",
            "Set your Target Role — be specific, e.g. 'Associate Product Manager'",
            "Add your Career Goals — what you want to achieve and by when",
            "Click Save Profile — this powers everything else in the app",
        ],
        "tip": "You only need to do this once. Come back to update your resume or goals anytime."
    },
    "Track": {
        "title": "Tracking your job pipeline",
        "steps": [
            "Click 'Add New Job' to log a job you're pursuing",
            "Fill in Company, Role, and Status at minimum",
            "Update the status as your application progresses",
            "Click on any job to edit it or delete it",
        ],
        "tip": "You must add a job here before you can score it in Match."
    },
    "Match": {
        "title": "Scoring your resume against a job",
        "steps": [
            "Select a job from your tracker in the dropdown",
            "Paste the full job description into the text area",
            "Click 'Score My Match'",
            "Review your match score, gaps, cert recommendations, and actions",
        ],
        "tip": "The scam check runs automatically before scoring. Check the verdict before investing time in an application."
    },
    "Guide": {
        "title": "Building your critical path",
        "steps": [
            "Click 'Generate Critical Path' to build your personalized roadmap",
            "Review your current state, target state, and gap summary",
            "Work through each milestone in order — check the box when complete",
            "Use the advisor chat to drill down on any milestone or question",
        ],
        "tip": "The critical path is generated fresh each session using your profile and match history. The more jobs you score in Match, the smarter it gets."
    },
    "app": {
        "title": "Getting started with Telos",
        "steps": [
            "Start with Profile — upload your resume and set your target role",
            "Go to Track — add the jobs you're currently pursuing",
            "Go to Match — score your resume against each job description",
            "Go to Guide — generate your critical path to your target role",
        ],
        "tip": "Follow the steps in order. Each pillar builds on the one before it."
    }
}

def show_help(page_name: str):
    from core.help_content import HELP_CONTENT
    content = HELP_CONTENT.get(page_name, HELP_CONTENT["app"])
    
    with st.sidebar:
        st.markdown("---")
        with st.expander("❓ Help — " + content["title"]):
            for i, step in enumerate(content["steps"], 1):
                st.markdown(f"**{i}.** {step}")
            st.markdown("---")
            st.info(f"💡 {content['tip']}")