"""
autofill_form Tool Handler.

Automatically fills form fields using AI extraction from:
- Uploaded source documents
- User profile data
- Default values and rules

Implements the Golden Flow: fill first, user edits later.
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle autofill_form tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form to fill
            - source_doc_ids: Optional list of source document IDs
            - use_profile: Whether to use user profile data (default: True)

    Returns:
        CallToolResult with fill summary (minimal per Golden Flow)
    """
    form_id = arguments.get("form_id")
    source_doc_ids = arguments.get("source_doc_ids", [])
    use_profile = arguments.get("use_profile", True)

    if not form_id:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Error: form_id is required"
            )]
        )

    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Error: No active session"
            )]
        )

    storage = MCPStorage()

    try:
        # Get the form
        form = await storage.get_form(session["id"], form_id)
        if not form:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error: Form not found: {form_id}"
                )]
            )

        # Get source documents if specified
        source_docs = []
        if source_doc_ids:
            for doc_id in source_doc_ids:
                doc = await storage.get_source_doc(session["id"], doc_id)
                if doc:
                    source_docs.append(doc)

        # Get all source docs for this session if none specified
        if not source_docs:
            source_docs = await storage.get_all_source_docs(session["id"])

        # Get user profile if requested and user is logged in
        profile = None
        if use_profile and session.get("user_id"):
            profile = await storage.get_user_profile(session["user_id"])

        # Perform auto-fill
        # This calls the actual extraction and mapping service
        fill_result = await _perform_autofill(
            form=form,
            source_docs=source_docs,
            profile=profile,
        )

        filled_count = fill_result.get("filled_count", 0)
        total_fields = fill_result.get("total_fields", 0)
        empty_count = total_fields - filled_count

        # Store updated form state
        await storage.update_form_fields(
            session_id=session["id"],
            form_id=form_id,
            fields=fill_result.get("fields", {}),
        )

        # Minimal response per Golden Flow
        response_text = f"Filled {filled_count} fields."

        if empty_count > 0:
            response_text += f" {empty_count} fields need your input."

        # Add confidence info for fields that might need review
        low_confidence_fields = fill_result.get("low_confidence_fields", [])
        if low_confidence_fields:
            response_text += f"\n\n⚠️ {len(low_confidence_fields)} fields have low confidence and may need review."

        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Error during auto-fill: {str(e)}"
            )]
        )


async def _perform_autofill(
    form: dict[str, Any],
    source_docs: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Perform the actual auto-fill operation.

    This integrates with the existing extraction and mapping services.

    Args:
        form: Form metadata with fields
        source_docs: List of source documents
        profile: User profile data (if available)

    Returns:
        Dict with:
            - filled_count: Number of fields filled
            - total_fields: Total number of fields
            - fields: Updated field values
            - low_confidence_fields: Fields with low extraction confidence
    """
    # Import the existing services
    from app.services.extract import extract_service
    from app.services.mapping import mapping_service

    fields = form.get("fields", {})
    total_fields = len(fields)
    filled_count = 0
    low_confidence_fields = []

    # Extract data from source documents
    extracted_data = {}
    for doc in source_docs:
        try:
            doc_extraction = await extract_service.extract_from_document(
                doc.get("path"),
                doc.get("mime_type", "application/pdf"),
            )
            extracted_data.update(doc_extraction.get("data", {}))
        except Exception:
            # Continue with other docs if one fails
            pass

    # Add profile data
    if profile:
        for key, value in profile.items():
            if key not in extracted_data:
                extracted_data[key] = {
                    "value": value,
                    "source": "profile",
                    "confidence": 1.0,
                }

    # Map extracted data to form fields
    for field_id, field_info in fields.items():
        field_name = field_info.get("name", field_id)
        field_type = field_info.get("type", "text")

        # Try to find a matching value
        matched_value = await mapping_service.find_best_match(
            field_name=field_name,
            field_type=field_type,
            extracted_data=extracted_data,
        )

        if matched_value:
            fields[field_id]["value"] = matched_value["value"]
            fields[field_id]["source"] = matched_value.get("source", "extracted")
            fields[field_id]["confidence"] = matched_value.get("confidence", 0.5)
            filled_count += 1

            if matched_value.get("confidence", 0.5) < 0.7:
                low_confidence_fields.append(field_id)

    return {
        "filled_count": filled_count,
        "total_fields": total_fields,
        "fields": fields,
        "low_confidence_fields": low_confidence_fields,
    }
