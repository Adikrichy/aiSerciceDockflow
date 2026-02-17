from app.llm.client import LlmClient


class WorkflowAiService:
    def __init__(self, llm_factory):
        self._llm_factory = llm_factory

    async def suggest(self, payload: dict) -> dict:
        """
        Expects payload: 
        {
          "prompt": "user description",
          "current_xml": "<workflow>...</workflow>", (optional)
          "available_roles": [{"name": "RoleA", "level": 10}, ...]
        }
        Returns: {"xml": "<workflow>...</workflow>"}
        """
        user_prompt = payload.get("prompt", payload.get("goal", "Unknown process"))
        current_xml = payload.get("current_xml")
        available_roles = payload.get("available_roles", [])
        provider = payload.get("provider")

        roles_context = ""
        if available_roles:
            roles_str = "\n".join([f"- {r['name']} (Level {r['level']})" for r in available_roles])
            roles_context = f"\nAVAILABLE ROLES IN THIS COMPANY (YOU MUST USE ONLY THESE):\n{roles_str}\n"
        else:
            roles_context = "\nCOMMON ROLES: Manager (60), CEO (100), Accountant (40), HR (50), Legal (70)\n"

        edit_instruction = ""
        if current_xml and len(current_xml.strip()) > 10:
            edit_instruction = (
                "CONTEXT: There is an EXISTING workflow provided below. "
                "The user wants to MODIFY it based on their description. "
                "1. If you update a step, keep its 'order' if possible.\n"
                "2. Remove any steps that no longer fit the new process.\n"
                "3. IMPORTANT: Update ALL routing rules (<onApprove>, etc.) to reflect the new logic. "
                "Do not leave steps disconnected.\n\n"
                f"CURRENT XML:\n{current_xml}\n\n"
            )
        else:
            edit_instruction = "CONTEXT: Build a NEW workflow from scratch based on the description.\n"

        system_instruction = (
            "You are a professional Business Process Architect.\n"
            "Your task is to convert a natural language description into a strictly formatted XML workflow.\n\n"
            f"{edit_instruction}\n"
            "CRITICAL GRAPH RULES:\n"
            "1. NO DISCONNECTED STEPS: Every step (except the absolute final ones) MUST have an outgoing transition (usually <onApprove>).\n"
            "2. SEQUENTIAL FLOW: If step 1 is followed by step 2, you MUST explicitly write <onApprove stepOrder=\"1\" targetStep=\"2\"/>. Never assume it's implicit.\n"
            "3. CONTINUITY: Ensure there is a path from the first step to the last. check that step 1 -> 2 -> 3 etc. actually exists in your XML output.\n\n"
            "ROLE RULES:\n"
            "1. Use ONLY the roles provided in the 'AVAILABLE ROLES' list. Map user roles like 'Accountant' to the most similar role in the list (e.g. 'Worker' or 'Accountant' if it exists).\n"
            "2. Each step 'roleLevel' MUST match the level in the list exactly.\n\n"
            f"{roles_context}\n"
            "XML SCHEMA:\n"
            "- <workflow> (root)\n"
            "- <step order=\"N\" roleName=\"R\" roleLevel=\"L\" action=\"approve/sign/review\" description=\"...\"/>\n"
            "- <onApprove stepOrder=\"N\" targetStep=\"M\" condition=\"$var > value\"/>\n"
            "- <onReject stepOrder=\"N\" targetStep=\"M\"/>\n"
            "- <onTimeout stepOrder=\"N\" targetStep=\"M\"/>\n\n"
            "OUTPUT ONLY THE XML. No explanations, no markdown blocks."
        )

        full_prompt = f"{system_instruction}\n\nUSER REQUEST:\n{user_prompt}"

        llm = self._llm_factory(provider) if provider else self._llm_factory()
        
        # We want raw XML, not JSON object
        xml_answer = await llm.generate(full_prompt, is_json=False)
        
        # Clean up any potential markdown backticks
        clean_xml = xml_answer.strip()
        if clean_xml.startswith("```xml"):
            clean_xml = clean_xml[6:]
        if clean_xml.startswith("```"):
            clean_xml = clean_xml[3:]
        if clean_xml.endswith("```"):
            clean_xml = clean_xml[:-3]
        
        return {"xml": clean_xml.strip()}