
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import LEDForConditionalGeneration, AutoTokenizer

app = FastAPI(title="Research Paper Summarization API")

# Load pipeline objects
tokenizer = AutoTokenizer.from_pretrained("./tokenizer")
model = LEDForConditionalGeneration.from_pretrained("./config")
model.load_state_dict(torch.load("led_base_scientific_summarizer.pth", map_location="cpu"))
model.eval()

class ArticleRequest(BaseModel):
    text: str

@app.post("/summarize")
def summarize(payload: ArticleRequest):
    try:
        inputs = tokenizer(payload.text, max_length=4096, return_tensors="pt", truncation=True)
        
        # Create global attention mask
        global_attention_mask = torch.zeros_like(inputs["input_ids"])
        global_attention_mask[:, 0] = 1
        
        with torch.no_grad():
            summary_ids = model.generate(
                inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                global_attention_mask=global_attention_mask,
                max_length=512,
                num_beams=4,
                early_stopping=True
            )
        summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
