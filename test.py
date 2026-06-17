from api.qa_service import answer_question
import json

def main():
    collection = "fastapi_fastapi"
    query = input("Enter query: ")
    claude_response = answer_question(question=query, collection_name=collection)
    print(json.dumps(claude_response, indent=2, default=str))

main()