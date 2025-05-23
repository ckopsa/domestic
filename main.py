# main.py
import uuid
from datetime import datetime, date as DateObject
from typing import Optional, List # Ensure List is imported

from dominate import document
from dominate.tags import *
from fastapi import FastAPI, HTTPException, Form, status, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

# Assuming these are in the same directory or your Python path is set up
from models import WIPDocument, WIPStatus, WIPUpdateData, BackgroundCheckStatus # Import Pydantic models
from repository import InMemoryWIPRepository, WIPRepository
from services import WIPService
from style import my_style # Your CSS

app = FastAPI()

# --- Dependencies ---
def get_wip_repository() -> WIPRepository:
    """Provides an instance of the WIPRepository."""
    return InMemoryWIPRepository()

def get_wip_service(repo: WIPRepository = Depends(get_wip_repository)) -> WIPService:
    """Provides an instance of the WIPService, injecting the repository."""
    return WIPService(repository=repo)

# --- Utility for HTML message/error pages ---
def create_message_page(
        title: str,
        heading: str,
        message: str,
        links: List[tuple[str, str]],
        status_code: int = 200
) -> HTMLResponse:
    """Helper function to generate simple HTML message pages."""
    doc = document(title=title)
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            # Determine heading color based on title content
            heading_style = "color: #48bb78;" # Default green for success
            if "error" in title.lower() or "fail" in title.lower():
                heading_style = "color: #ef4444;" # Red for error/failure
            elif "warn" in title.lower(): # Orange for warning
                heading_style = "color: #f6ad55;"

            h1(heading, style=heading_style)
            p(message)
            for link_text, link_href in links:
                a(link_text, href=link_href, cls='back-link', style="margin-right:15px; display:inline-block; margin-top:10px;")
    return HTMLResponse(content=doc.render(), status_code=status_code)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the homepage."""
    doc = document(title='WIP Management System')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Welcome to the WIP Management System!')
            p('Manage your Work-in-Progress documents efficiently.')
            h2('Get Started:')
            with ul():
                li(a('List All WIP Documents', href='/wip', cls='action-button'))
                li(a('Create New WIP Document', href='/create-wip', cls='action-button create-wip-link'))
            # Example items (can be removed if not needed for main app)
            h2('Example Items (Demo):')
            with ul():
                li(a('Item 1', href='/items/1'))
                li(a('Item 2', href='/items/2'))
    return doc.render()

@app.get("/items/{item_id}", response_class=HTMLResponse)
async def read_item_example(item_id: int): # Renamed to avoid conflict if items become a real feature
    """Serves an example item detail page (demo)."""
    items_data = {
        1: {"name": "Demo Laptop", "description": "Powerful laptop for work and gaming demonstrations."},
        2: {"name": "Demo Smartphone", "description": "Latest model smartphone with advanced features for demo."},
    }
    item = items_data.get(item_id)
    if not item:
        return create_message_page("Item Not Found", "Error 404", "The requested demo item was not found.", [("← Back to Home", "/")], status_code=404)

    doc = document(title=f'Item Details: {item["name"]}')
    with doc.head: style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'Details for {item["name"]}')
            p(f'ID: {item_id}')
            p(f'Description: {item["description"]}')
            a('← Back to Home', href='/', cls='back-link')
    return doc.render()

@app.get("/create-wip", response_class=HTMLResponse)
async def create_wip_page():
    """Renders the HTML form to create a new WIP document."""
    doc = document(title='Create New WIP')
    with doc.head: style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Create New Work-in-Progress Document')
            with form(action="/submit-create-wip", method="post"):
                with div():
                    label('WIP Title:', fr='wip_title')
                    input_(type='text', id='wip_title', name='wip_title', required=True)
                with div():
                    label('Owner Name:', fr='wip_owner')
                    input_(type='text', id='wip_owner', name='wip_owner', required=True)
                with div(): # Date created is now defaulted in the model/service
                    label('Due Date (Optional):', fr='due_date')
                    input_(type='date', id='due_date', name='due_date_str') # Name it _str for clarity
                button('Create WIP Document', type='submit', cls="action-button create-wip-link")
            a('← Back to WIP List', href='/wip', cls='back-link')
            a('← Back to Home', href='/', cls='back-link', style="margin-left:15px;")
    return doc.render()

@app.post("/submit-create-wip")
async def submit_create_wip_handler(
        wip_title: str = Form(...),
        wip_owner: str = Form(...),
        due_date_str: Optional[str] = Form(None), # Form sends date as string
        service: WIPService = Depends(get_wip_service)
):
    """Handles the submission of the create WIP form."""
    try:
        # Service layer will handle default dateCreated
        due_date_obj = DateObject.fromisoformat(due_date_str) if due_date_str else None
    except ValueError:
        return create_message_page("Invalid Input", "Creation Failed", "Invalid due date format provided.", [("← Try Again", "/create-wip")], status_code=400)

    wip_doc = await service.create_new_wip(
        title=wip_title,
        owner=wip_owner,
        date_created=DateObject.today(),
        due_date=due_date_obj
    )
    return RedirectResponse(url=f"/wip/{wip_doc.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/wip/{wip_id}", response_class=HTMLResponse)
async def read_wip_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    """Retrieves and displays a single WIP document."""
    wip_doc = await service.get_wip_by_id(wip_id)
    if not wip_doc:
        return create_message_page("WIP Not Found", "Error 404", f"WIP Document with ID '{wip_id}' not found.", [("← Back to WIP List", "/wip")], status_code=404)

    doc = document(title=f'WIP: {wip_doc.title}')
    with doc.head: style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'WIP Document: {wip_doc.title}')
            with div(cls='wip-details'):
                p(strong('ID:'), f' {wip_doc.id}')
                p(strong('Owner:'), f' {wip_doc.owner}')
                p(strong('Date Created:'), f' {wip_doc.dateCreated.isoformat()}')
                p(strong('Due Date:'), f' {wip_doc.dueDate.isoformat() if wip_doc.dueDate else "Not set"}')
                p(strong('Status:'), f' {wip_doc.status.upper()}')
                if wip_doc.status == "archived":
                    p(strong("Note:"), " This WIP document is archived and read-only.", style="color: #718096;")

                h3("Collected Data", style="margin-top:20px; font-size:1.1em;")
                p(strong('Employee Name:'), f' {wip_doc.employee_name or "N/A"}')
                p(strong('Employee Email:'), f' {wip_doc.employee_email or "N/A"}')
                p(strong('Interview Notes:'), f' {wip_doc.interview_notes or "N/A"}')
                p(strong('Background Check Status:'), f' {wip_doc.background_check_status.upper()}')
                p(strong('Contract Details:'), f' {wip_doc.contract_details or "N/A"}')

            if wip_doc.status not in ["submitted", "canceled", "archived"]:
                with div(cls='sub-steps', style="margin-top:20px;"):
                    h2('Data Collection Steps:')
                    with ul():
                        li(a('Employee Data', href=f'/wip/{wip_id}/employee-data'))
                        li(a('Interview Results', href=f'/wip/{wip_id}/interviews'))
                        li(a('Background Check', href=f'/wip/{wip_id}/background-check'))
                        li(a('Contract Details', href=f'/wip/{wip_id}/contract'))

                if wip_doc.status in ["draft", "working"]:
                    with div(cls='update-metadata-section section-box', style="margin-top:20px;"): # Added section-box class
                        h3('Update Due Date')
                        with form(action=f"/wip/{wip_id}/update-data", method="post"):
                            input_(type='hidden', name='form_source', value='update_due_date_main')
                            with div(style="display:flex; align-items:center; margin-bottom:10px;"):
                                label('Due Date:', fr='due_date_update_field', style="margin-bottom:0; margin-right:10px; white-space:nowrap;")
                                input_(type='date', id='due_date_update_field', name='due_date_str', value=wip_doc.dueDate.isoformat() if wip_doc.dueDate else "")
                            button('Set/Update Due Date', type='submit', cls="action-button")

            if wip_doc.status not in ["archived"]: # Actions section
                with div(cls='wip-actions section-box', style="margin-top:20px;"):
                    h2('WIP Actions:')
                    action_buttons_exist = False
                    if wip_doc.status not in ["submitted", "canceled"]:
                        action_buttons_exist = True
                        with form(action=f"/wip/{wip_id}/submit", method="post", style="display:inline-block; margin-right:10px;"):
                            button('Submit WIP', type='submit', cls='action-button submit')
                        with form(action=f"/wip/{wip_id}/cancel", method="post", style="display:inline-block;"):
                            button('Cancel WIP', type='submit', cls='action-button cancel')

                    if wip_doc.status in ["draft", "working"]:
                        action_buttons_exist = True
                        div_share_style = "margin-top:20px;" if wip_doc.status not in ["submitted", "canceled"] else "" # Add margin if other buttons are above
                        with div(cls="share-section", style=div_share_style):
                            h3('Share this WIP Document', style="font-size:1.1em; margin-bottom:5px;")
                            with form(action=f"/wip/{wip_id}/share", method="post"):
                                with div(style="display:flex; align-items:center; margin-bottom:10px;"):
                                    label('Share with (Email):', fr='share_with_email', style="margin-bottom:0; margin-right:10px;")
                                    input_(type='email', id='share_with_email', name='share_with_email', required=True, placeholder="Enter email address")
                                button('Share WIP', type='submit', cls='action-button share')

                    if wip_doc.status in ["submitted", "canceled"]:
                        action_buttons_exist = True
                        with form(action=f"/wip/{wip_id}/archive", method="post", style="display:inline-block; margin-top:20px;"):
                            button('Archive WIP', type='submit', cls='action-button archive') # Added class for styling

                    if not action_buttons_exist:
                        p("No further actions available for this WIP's current status.")

            a('← Back to WIP List', href='/wip', cls='back-link', style="margin-top:20px; display:inline-block;")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()

@app.get("/wip", response_class=HTMLResponse)
async def list_wips_handler(
        filter_title: Optional[str] = None, filter_owner: Optional[str] = None, filter_status: Optional[str] = None,
        due_after_str: Optional[str] = None, due_before_str: Optional[str] = None, filter_overdue_str: Optional[str] = None,
        service: WIPService = Depends(get_wip_service)
):
    """Generates a list of WIP documents, with filtering options."""
    try:
        due_after = DateObject.fromisoformat(due_after_str) if due_after_str else None
        due_before = DateObject.fromisoformat(due_before_str) if due_before_str else None
    except ValueError: # Handle invalid date strings from query params gracefully
        due_after, due_before = None, None
        # Optionally, add a message to the user if dates are invalid
    filter_overdue = True if filter_overdue_str == 'true' else False

    filtered_wips = await service.get_filtered_wips(
        filter_title, filter_owner, filter_status, due_after, due_before, filter_overdue
    )

    doc = document(title='Work-in-Progress Documents')
    with doc.head: style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Work-in-Progress Documents')
            with div(cls='filter-form section-box'):
                h2('Filter WIPs')
                with form(action="/wip", method="get"):
                    with div(): label('Title Contains:', fr='filter_title'); input_(type='text', id='filter_title', name='filter_title', value=filter_title or "")
                    with div(): label('Owner Contains:', fr='filter_owner'); input_(type='text', id='filter_owner', name='filter_owner', value=filter_owner or "")
                    with div():
                        label('Status:', fr='filter_status')
                        with select(id='filter_status', name='filter_status'):
                            option("Active (Default)", value="", selected=(not filter_status)) # Default for filter_status = None or ""
                            # Dynamically list all possible statuses from the Literal type
                            for stat_val in WIPStatus.__args__: # type: ignore
                                option(stat_val.capitalize(), value=stat_val, selected=(filter_status == stat_val))
                            option("All Statuses", value="all", selected=(filter_status == "all"))
                    with div(): label('Due On/After:', fr='due_after'); input_(type='date', id='due_after', name='due_after_str', value=due_after_str or "")
                    with div(): label('Due On/Before:', fr='due_before'); input_(type='date', id='due_before', name='due_before_str', value=due_before_str or "")
                    with div(style="padding-top: 5px; display:flex; align-items:center;"):
                        input_(type='checkbox', id='filter_overdue', name='filter_overdue_str', value='true', checked=(filter_overdue_str == 'true'), style="width:auto; margin-right:5px;")
                        label('Show Overdue Only', fr='filter_overdue', style="display:inline; font-weight:normal; color:#333; margin-bottom:0;")

                    button('Filter', type='submit', cls="action-button", style="margin-top:10px;")
                    if any([filter_title, filter_owner, filter_status, due_after_str, due_before_str, filter_overdue_str]):
                        a('Clear Filters', href='/wip', style="margin-left: 10px; color: #4a5568; text-decoration: underline; font-size:0.9em; vertical-align:middle;")

            if not filtered_wips:
                p('No WIP documents match your filters, or no WIPs exist.')
            else:
                with ul():
                    today = DateObject.today()
                    for wip in filtered_wips:
                        with li(cls='wip-list-item'):
                            p(strong('Title:'), f' {wip.title}')
                            p(strong('Owner:'), f' {wip.owner}')
                            due_display = wip.dueDate.isoformat() if wip.dueDate else "N/A"
                            is_overdue = wip.dueDate and wip.dueDate < today and wip.status in ["draft", "working"]
                            p(strong('Due:'), span(f"{due_display} {'(OVERDUE)' if is_overdue else ''}",
                                                   style="color:red; font-weight:bold;" if is_overdue else ""))
                            p(strong('Status:'), f' {wip.status.upper()}')
                            p(strong('Created:'), f' {wip.dateCreated.isoformat()}')
                            a('View Details', href=f'/wip/{wip.id}', cls='action-button view-details')

            a('Create New WIP Document', href='/create-wip', cls='create-wip-link action-button', style="margin-top:20px;")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; margin-left:15px; display:inline-block;")
    return doc.render()

@app.post("/wip/{wip_id}/update-data")
async def update_wip_data_handler(
        wip_id: str,
        service: WIPService = Depends(get_wip_service),
        # Form fields for various sub-forms.
        employee_name: Optional[str] = Form(None),
        employee_email: Optional[str] = Form(None),
        interview_notes: Optional[str] = Form(None),
        background_check_status_str: Optional[str] = Form(None), # String from form
        contract_details: Optional[str] = Form(None),
        due_date_str: Optional[str] = Form(None), # String from form, can be ""
        form_source: Optional[str] = Form(None) # To identify which form posted, if needed
):
    """Handles data updates from various sub-forms or the due date update form."""
    due_date_obj: Optional[DateObject] = None
    if due_date_str is not None: # Explicitly submitted (even if "")
        try:
            due_date_obj = DateObject.fromisoformat(due_date_str) if due_date_str else None
        except ValueError:
            return create_message_page("Update Failed", "Update Failed!", "Invalid due date format.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)

    bg_status_obj: Optional[BackgroundCheckStatus] = None
    if background_check_status_str:
        if background_check_status_str not in BackgroundCheckStatus.__args__: # type: ignore
            return create_message_page("Update Failed", "Update Failed!", "Invalid background check status.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
        bg_status_obj = background_check_status_str # type: ignore

    update_payload = WIPUpdateData(
        employee_name=employee_name, employee_email=employee_email,
        interview_notes=interview_notes, background_check_status=bg_status_obj,
        contract_details=contract_details, due_date=due_date_obj
    )

    try:
        updated_wip = await service.update_wip_data(wip_id, update_payload)
        if not updated_wip: # Should not happen if service raises ValueError for business logic errors
            raise HTTPException(status_code=404, detail="WIP not found or update failed unexpectedly.")
        return RedirectResponse(url=f"/wip/{wip_id}", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page("Update Failed", "Update Failed!", str(e), [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
    except Exception as e_gen: # Catch any other unexpected error
        # Log e_gen for debugging
        return create_message_page("Update Error", "An Unexpected Error Occurred", "Could not update the WIP document.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=500)

@app.post("/wip/{wip_id}/submit")
async def submit_wip_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try:
        await service.submit_wip(wip_id)
        return RedirectResponse(url=f"/wip/{wip_id}", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page("Submission Failed", "Submission Failed!", str(e), [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
    except Exception:
        return create_message_page("Submission Error", "Submission Error", "WIP not found or another error occurred.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=404)

@app.post("/wip/{wip_id}/cancel")
async def cancel_wip_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try:
        await service.cancel_wip(wip_id)
        return RedirectResponse(url=f"/wip/{wip_id}", status_code=status.HTTP_303_SEE_OTHER) # Or redirect to /wip
    except ValueError as e: # If service raises error for trying to cancel non-cancellable
        return create_message_page("Cancel Failed", "Cancel Failed!", str(e), [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
    except Exception:
        return create_message_page("Cancel Error", "Cancel Error", "WIP not found or another error occurred.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=404)

@app.post("/wip/{wip_id}/archive")
async def archive_wip_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try:
        await service.archive_wip(wip_id)
        return create_message_page("WIP Archived", "WIP Document Archived",
                                   "The WIP document has been successfully archived.",
                                   [(f"← View WIP", f"/wip/{wip_id}"), ("← WIP List", "/wip")])
    except ValueError as e:
        return create_message_page("Archive Failed", "Archive Failed!", str(e), [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
    except Exception:
        return create_message_page("Archive Error", "Archive Error", "WIP not found or another error occurred.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=404)

@app.post("/wip/{wip_id}/share")
async def share_wip_handler(wip_id: str, share_with_email: str = Form(..., min_length=3), service: WIPService = Depends(get_wip_service)):
    try:
        wip_doc = await service.share_wip(wip_id, share_with_email)
        return create_message_page("WIP Shared", "WIP Document Shared",
                                   f"WIP '{wip_doc.title}' notionally shared with {share_with_email}.",
                                   [(f"← Back to WIP", f"/wip/{wip_id}"), ("← WIP List", "/wip")])
    except ValueError as e:
        return create_message_page("Share Failed", "Share Failed!", str(e), [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=400)
    except Exception:
        return create_message_page("Share Error", "Share Error", "WIP not found or another error occurred.", [(f"← Back to WIP", f"/wip/{wip_id}")], status_code=404)


# --- Sub-step GET pages (Forms that POST to /update-data) ---
async def _render_sub_step_form(wip_doc: WIPDocument, page_title_suffix: str, form_fields_html: callable):
    doc = document(title=f'WIP: {wip_doc.title} - {page_title_suffix}')
    with doc.head: style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'{page_title_suffix} for "{wip_doc.title}"')
            with form(action=f"/wip/{wip_doc.id}/update-data", method="post"):
                input_(type='hidden', name='form_source', value=page_title_suffix.lower().replace(" ", "_"))
                form_fields_html(wip_doc) # Call the passed function to generate specific fields
                button('Save Changes', type='submit', cls="action-button")
            a(f'← Back to WIP Document', href=f'/wip/{wip_doc.id}', cls='back-link')
    return HTMLResponse(content=doc.render())

async def _get_wip_for_substep(wip_id: str, service: WIPService) -> WIPDocument:
    wip_doc = await service.get_wip_by_id(wip_id)
    if not wip_doc:
        raise HTTPException(status_code=404, detail="WIP Document not found")
    if wip_doc.status in ["submitted", "canceled", "archived"]:
        # This redirect will be caught by FastAPI if it's a GET request,
        # but better to handle the redirection in the calling route or return an error page
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, detail="Not editable", headers={"Location": f"/wip/{wip_id}"})
    return wip_doc

@app.get("/wip/{wip_id}/employee-data", response_class=HTMLResponse)
async def employee_data_page_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try:
        wip_doc = await _get_wip_for_substep(wip_id, service)
    except HTTPException as e: # Catch the redirect exception
        if e.status_code == status.HTTP_303_SEE_OTHER:
            return RedirectResponse(url=e.headers["Location"], status_code=e.status_code)
        raise e

    def fields(doc_data: WIPDocument):
        with div():
            label('Employee Full Name:', fr='employee_name')
            input_(type='text', id='employee_name', name='employee_name', value=doc_data.employee_name or "", required=True)
        with div():
            label('Employee Email:', fr='employee_email')
            input_(type='email', id='employee_email', name='employee_email', value=doc_data.employee_email or "", required=True)
    return await _render_sub_step_form(wip_doc, "Employee Data", fields)

@app.get("/wip/{wip_id}/interviews", response_class=HTMLResponse)
async def interviews_page_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try: wip_doc = await _get_wip_for_substep(wip_id, service)
    except HTTPException as e: return RedirectResponse(url=e.headers["Location"], status_code=e.status_code) if e.status_code == 303 else (_ for _ in ()).throw(e) # type: ignore

    def fields(doc_data: WIPDocument):
        with div():
            label('Interview Notes:', fr='interview_notes')
            textarea(doc_data.interview_notes or "", id='interview_notes', name='interview_notes', rows="8")
    return await _render_sub_step_form(wip_doc, "Interview Notes", fields)

@app.get("/wip/{wip_id}/background-check", response_class=HTMLResponse)
async def background_check_page_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try: wip_doc = await _get_wip_for_substep(wip_id, service)
    except HTTPException as e: return RedirectResponse(url=e.headers["Location"], status_code=e.status_code) if e.status_code == 303 else (_ for _ in ()).throw(e) # type: ignore

    def fields(doc_data: WIPDocument):
        with div():
            label('Background Check Status:', fr='background_check_status_str')
            with select(id='background_check_status_str', name='background_check_status_str'):
                current_bg_status = doc_data.background_check_status
                for stat_val in BackgroundCheckStatus.__args__: # type: ignore
                    option(stat_val.replace("_", " ").capitalize(), value=stat_val, selected=(current_bg_status == stat_val))
    return await _render_sub_step_form(wip_doc, "Background Check Status", fields)

@app.get("/wip/{wip_id}/contract", response_class=HTMLResponse)
async def contract_page_handler(wip_id: str, service: WIPService = Depends(get_wip_service)):
    try: wip_doc = await _get_wip_for_substep(wip_id, service)
    except HTTPException as e: return RedirectResponse(url=e.headers["Location"], status_code=e.status_code) if e.status_code == 303 else (_ for _ in ()).throw(e) # type: ignore

    def fields(doc_data: WIPDocument):
        with div():
            label('Contract Details:', fr='contract_details')
            textarea(doc_data.contract_details or "", id='contract_details', name='contract_details', rows="8")
    return await _render_sub_step_form(wip_doc, "Contract Details", fields)