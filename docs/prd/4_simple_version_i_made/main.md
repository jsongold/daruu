[document,,,] = split_document_into_pages(documents)
is_valid = validate_document(document)
skip_document = not is_valid
user_info = parse_user_data(user_info)
prompt = generate_prompt_this_document(document) -- this prompt is the rule
form_fields = fill(user_info,prompt)
structured_document = render_document(form_fields)

questions = generate_questions(structured_document)
user_info = ask_user(questions)
form_fields = fill(user_info,prompt)
structured_document = render_document(form_fields)
