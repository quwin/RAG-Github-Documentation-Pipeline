from api.qa_service import answer_question
from api.ingest_service import ingest_repo
import json

## Simple test workflow used for quwin.dev website for ease-of-use
def main():
    ingest_repo(repo_url="https://github.com/quwin/RAG-Github-Documentation-Pipeline",recursive_chunking=False, erase_prior_embeddings=True)
    ingest_repo(repo_url="https://github.com/quwin/quwin",recursive_chunking=False, erase_prior_embeddings=True)
    ingest_repo(repo_url="https://github.com/quwin/quwin.dev",recursive_chunking=False, erase_prior_embeddings=True)
    ingest_repo(repo_url="https://github.com/quwin/Belevator-Tactics",recursive_chunking=False, erase_prior_embeddings=True)
    ingest_repo(repo_url="https://github.com/quwin/infiniport.al",recursive_chunking=False, erase_prior_embeddings=True)
    ingest_response = ingest_repo(repo_url="https://github.com/quwin/UnderTheGun",recursive_chunking=False, erase_prior_embeddings=True)
    print(json.dumps(ingest_response, indent=2, default=str))
    # collection = "quwin_RAG-Github-Documentation-Pipeline"
    # query = input("Enter query: ")
    # claude_response = answer_question(question=query, collection_name=collection)
    # print(json.dumps(claude_response, indent=2, default=str))

main()