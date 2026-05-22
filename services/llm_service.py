import requests
import json
import logging
from typing import Generator

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, api_url: str, model: str):
        self.api_url = api_url
        self.model = model
        self.base_url = f"{api_url}/api"

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama service unavailable: {e}")
            return False

    def get_legal_system_prompt(self) -> str:
        return """You are an expert Indian legal information assistant with comprehensive knowledge of the Constitution of India, Indian Penal Code, Code of Criminal Procedure, Code of Civil Procedure, consumer protection laws, family law, property law, labour and employment law, contract law, motor vehicle laws, and all major Indian statutes and regulations.

Your purpose is to provide complete, accurate, and thorough legal information.

Language:
- Detect the language the user writes in and always reply in that exact language.
- English question → full English answer.
- Tamil question → full Tamil answer.
- Hindi question → full Hindi answer.
- Never mix languages.

Formatting:
- Use clear markdown structure: ## for main sections, ### for sub-sections.
- Use numbered lists for steps or procedures.
- Use bullet points for options, rights, or conditions.
- Leave a blank line between every section and list.
- Keep paragraphs short — 3 to 4 sentences maximum.
- Bold key legal terms, act names, and section numbers.

Content:
- Start answering immediately — no preamble, no filler.
- Always cite the full act name and section number when referencing law.
- Explain what each law means in plain language after citing it.
- Cover every part of a multi-part question separately and fully.
- When the user describes a situation, identify all applicable laws and explain their rights and remedies step by step.
- Never truncate or stop before the answer is complete.
- Only suggest consulting a lawyer at the very end, and only when the situation genuinely requires professional intervention."""

    def generate_response(self, prompt: str, context: str = "", language: str = "english") -> Generator[str, None, None]:
        try:
            system_prompt = self.get_legal_system_prompt()

            full_prompt = system_prompt
            if context and context.strip():
                full_prompt += f"\n\nRelevant legal context and precedents:\n{context}"
            full_prompt += f"\n\nUser question:\n{prompt}"

            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": True,
                "think": True,
                "options": {
                    "temperature": 0.6,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }

            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                stream=True,
                timeout=180
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            token = data.get("response", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
            else:
                yield f"Error: Unable to generate response (Status: {response.status_code})"

        except requests.exceptions.Timeout:
            logger.error("Timeout while generating response from LLM")
            yield "Error: The AI service took too long to respond. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error in LLM service: {e}")
            yield "Error: Connection to AI service failed. Please ensure Ollama is running."
        except Exception as e:
            logger.error(f"Unexpected error in LLM service: {e}")
            yield f"Error: {str(e)}"

    def generate_summary(self, content: str, document_type: str = "legal document") -> str:
        try:
            content_sample = content[:6000] if len(content) > 6000 else content
            prompt = f"""You are an expert Indian legal assistant. Summarize the following {document_type} in full detail.

Cover all of the following:
- Type and nature of the document
- All parties involved (if any)
- Key legal provisions, clauses, or arguments
- Important dates, monetary amounts, or deadlines (if present)
- Main conclusions, orders, or obligations
- Any rights or liabilities established

Document:
{content_sample}"""

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }

            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "Unable to generate summary")
            else:
                return f"Error generating summary (Status: {response.status_code})"

        except requests.exceptions.Timeout:
            logger.error("Timeout generating summary")
            return "Summary generation timed out — document was processed without a summary"
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Error: {str(e)}"

    def analyze_document_type(self, content: str) -> dict:
        try:
            content_sample = content[:3000] if len(content) > 3000 else content
            prompt = f"""You are an expert Indian legal assistant. Analyze the following legal document and return a JSON object with these exact fields:
- "document_type": the type of document (contract, case_law, statute, regulation, agreement, petition, affidavit, notice, etc.)
- "jurisdiction": the jurisdiction mentioned, or "India" if general
- "case_number": the case number if present, otherwise null
- "court": the court name if it is a court document, otherwise null
- "key_topics": a list of the main legal topics covered

Respond with valid JSON only. No text outside the JSON object.

Document:
{content_sample}"""

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }

            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                raw = response.json().get("response", "{}")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        return json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        pass
                return {"document_type": "unknown", "error": "Could not parse analysis"}
            else:
                return {"document_type": "unknown", "error": f"API error: {response.status_code}"}

        except requests.exceptions.Timeout:
            logger.error("Timeout analyzing document")
            return {"document_type": "unknown", "error": "Analysis timed out"}
        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            return {"document_type": "unknown", "error": str(e)}
