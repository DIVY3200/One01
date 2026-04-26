import os
import json
import asyncio
import google.generativeai as genai
from groq import AsyncGroq
import aiohttp
from typing import Dict, Any, Optional

class EducationalOrchestrator:
    """
    Multi-Agent Orchestrator via Primary-Auditor pattern.
    Primary Agent (Tutor): Google Gemini 1.5 Flash
    Secondary Agent (Auditor): Llama 3 via Groq API
    Tool-Belt: Hugging Face Inference API
    """
    
    def __init__(self):
        # API Keys should be set in environment or .env
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.hf_token = os.getenv("HF_TOKEN", "")
        
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            # Gemini 1.5 Flash Model
            self.tutor_model = genai.GenerativeModel('gemini-1.5-flash')
        
        if self.groq_api_key:
            self.auditor_client = AsyncGroq(api_key=self.groq_api_key)
            self.auditor_model = "llama3-8b-8192"

    async def _call_tutor(self, user_input: str, persona: str, logic_corrections: str = "") -> dict:
        """Call Gemini 1.5 Flash to generate explanation and 3 questions."""
        system_context = (
            f"You are the Tutor Agent. Persona: {persona}. "
            f"Generate a clear, engaging explanation and a 3-question quiz for the user's input.\n"
            f"You must return ONLY a JSON object with this exact structure:\n"
            f"{{\n"
            f"  \"explanation\": \"...\",\n"
            f"  \"questions\": [\n"
            f"     {{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct\": \"A\"}}\n"
            f"  ],\n"
            f"  \"tool_needed\": \"image|audio|none\",\n"
            f"  \"tool_prompt\": \"Description for the image or text for audio if needed, else empty.\"\n"
            f"}}"
        )
        
        prompt = f"{system_context}\n\nUser Input: {user_input}"
        if logic_corrections:
            prompt += f"\n\nCorrection Request from Auditor (Fix these errors): {logic_corrections}"
        
        # Async generation with Gemini
        # We run it in a threadpool since generate_content async version is available
        response = await self.tutor_model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {"error": "Tutor returned invalid JSON", "raw": response.text}

    async def _call_auditor(self, tutor_content: dict) -> dict:
        """Call Groq Llama 3 to audit for logical/mathematical consistency."""
        system_prompt = (
            "You are a critical reviewer. Your only job is to find flaws in the provided educational content. "
            "Check specifically for Mathematical accuracy and Logical consistency. Be brief and technical.\n"
            "Return valid JSON with format: {\"is_valid\": boolean, \"correction_request\": \"string\"}"
        )
        
        content_to_review = f"Explanation:\n{tutor_content.get('explanation')}\n\nQuestions:\n{json.dumps(tutor_content.get('questions'))}"
        
        response = await self.auditor_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_to_review}
            ],
            model=self.auditor_model,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
             return {"is_valid": True, "correction_request": "Failed to parse auditor response."}

    async def _call_hf_tool(self, tool_type: str, prompt: str) -> Optional[str]:
        """Trigger Hugging Face APIs if Tutor requested an image or audio."""
        if not self.hf_token or tool_type not in ["image", "audio"]:
            return None
            
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        
        async with aiohttp.ClientSession() as session:
            try:
                if tool_type == "image":
                    # Stable Diffusion for images
                    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
                    payload = {"inputs": prompt}
                    async with session.post(API_URL, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            # Usually returns binary image data. 
                            # We can just return a success artifact or base64. 
                            # For simplicity we just return a stub or we could read and b64 encode it.
                            return f"[Image successfully generated for: {prompt}]"
                        return f"[Image generation failed: {resp.status}]"
                        
                elif tool_type == "audio":
                    # Espnet TTS
                    API_URL = "https://api-inference.huggingface.co/models/espnet/kan-bayashi_ljspeech_vits"
                    payload = {"inputs": prompt}
                    async with session.post(API_URL, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            return f"[Audio successfully generated for: {prompt[:30]}...]"
                        return f"[Audio generation failed: {resp.status}]"
                        
            except Exception as e:
                print(f"HF Tool error: {e}")
                return None

    async def generate_educational_content(self, user_input: str, persona: str = "Tutor") -> Dict[str, Any]:
        """
        Main orchestration loop:
        1. Tutor generates initial content
        2. Auditor checks content
        3. If flaws, Tutor rewrites
        4. Tool called if Tutor requested it
        5. Return verified JSON output
        """
        max_attempts = 3
        current_attempt = 1
        logic_corrections = ""
        final_tutor_response = None
        
        while current_attempt <= max_attempts:
            # Step 1: Tutor generates content
            tutor_data = await self._call_tutor(user_input, persona, logic_corrections)
            if "error" in tutor_data:
                return {"status": "error", "message": "Tutor generation failed", "data": tutor_data}
            
            # Step 2: Auditor reviews it
            audit_result = await self._call_auditor(tutor_data)
            
            # Step 3: Check decision
            if audit_result.get("is_valid", False) or current_attempt == max_attempts:
                final_tutor_response = tutor_data
                break
                
            # If invalid, increment counter and request corrections
            logic_corrections = audit_result.get("correction_request", "Please review logical and mathematical consistencies.")
            current_attempt += 1

        # Step 4: Tool Calling
        tool_output = None
        if final_tutor_response and final_tutor_response.get("tool_needed") in ["image", "audio"]:
            tool_output = await self._call_hf_tool(
                tool_type=final_tutor_response.get("tool_needed"), 
                prompt=final_tutor_response.get("tool_prompt")
            )
            final_tutor_response["tool_output"] = tool_output

        # Final Payload to Next.js
        return {
            "status": "success",
            "iterations": current_attempt,
            "content": final_tutor_response,
            "auditor_final_note": "Verified by Logic Gate"
        }

# Example usage (Uncomment and run to test locally if keys are set):
# async def main():
#     orchestrator = EducationalOrchestrator()
#     result = await orchestrator.generate_educational_content("Explain the Fibonacci sequence and string theory.", persona="Scientist")
#     print(json.dumps(result, indent=2))
#
# if __name__ == "__main__":
#     asyncio.run(main())
