import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM
from qdrant_client.models import SparseVector

_MODEL_CACHE = {}

def get_splade_model(model_id: str):
    if model_id not in _MODEL_CACHE:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForMaskedLM.from_pretrained(model_id)
        model.eval()
        _MODEL_CACHE[model_id] = (tokenizer, model)
    return _MODEL_CACHE[model_id]


def compute_sparse_vector(
    text: str,
    model_id: str = "naver/splade-cocondenser-ensembledistil",
) -> SparseVector:
    tokenizer, model = get_splade_model(model_id)
    tokens = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
        output = model(**tokens)
    logits = output.logits
    attention_mask = tokens["attention_mask"]
    # SPLADE-style pooling:
    # max over sequence of log(1 + relu(logits)), masked by attention.
    relu_log = torch.log1p(torch.relu(logits))
    weighted_log = relu_log * attention_mask.unsqueeze(-1)
    max_values, _ = torch.max(weighted_log, dim=1)
    vec = max_values.squeeze(0)
    # Convert dense vocab-sized tensor to Qdrant sparse format.
    nonzero = torch.nonzero(vec, as_tuple=True)[0]
    indices = nonzero.cpu().tolist()
    values = vec[nonzero].cpu().tolist()
    return SparseVector(
        indices=indices,
        values=values,
    )