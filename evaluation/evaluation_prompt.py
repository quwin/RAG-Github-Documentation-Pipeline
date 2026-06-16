def format_to_citation_response(content: list[dict]) -> list[dict]:
    citations = []
    for i, responses in enumerate(content):
        if (in_text := responses.get("citations")) is not None:
            citations.append({
                "type": "text",
                "text": f"""Citation index: {i}
                    Claim: {responses["text"]}
                    Cited Texts: {". ".join(cite.get("cited_text") for cite in in_text) }
                """
            })
    return citations

def system_eval_prompt() -> str:
    return """You are a careful evaluation assistant for a Retrieval-Augmented Generation system.
    
        You are verifying whether a cited source supports a claim.
        You also are evaluating the overall relevance of the search results to the orginal question.
        You also are scoring the response's completeness in answering the original question.

        Rules:
        1. valid_citations contains the indicies of the citations in which the cited text directly proves the claim.
        2. invalid_citations contains the indicies of the citations in which the cited text does not or only partially proves the claim.
        3. The retrieval_confidence ranges from 0.0-1.0, and is the overall relevance of the retrieved search results to the original question. 
        4. The answer_completeness ranges from 0.0-1.0, and is the score of the response's coverage in answering the original question. 
    """

def build_eval_message(query: str, response_content: list[dict]) -> list[dict]:
    eval_content = [{"type": "text", "text": system_eval_prompt()}]
    citation_blocks = format_to_citation_response(response_content)
    eval_content.extend(citation_blocks)
    full_response_text = ". ".join(
        block.get("text", "")
        for block in response_content
        if block.get("type") == "text"
    )
    eval_content.append({
        "type": "text",
        "text": f"Original query: {query}",
    })
    eval_content.append({
        "type": "text",
        "text": f"Full response: {full_response_text}",
    })
    if not citation_blocks:
        eval_content.append({
            "type": "text",
            "text": "No citations were found in the response content.",
        })
    return [{
        "role": "user",
        "content": eval_content,
    }]