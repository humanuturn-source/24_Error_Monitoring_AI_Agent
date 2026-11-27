"""
agents.py
LangGraph Multi-Agent Workflow for Local UI Error Checking:
- Router (gemma2): Classifies whether a browser inspection is needed
- Inspector (gemma4 + LocalBrowserAgent): Plans & runs Playwright inspection on target page/form
- Rule Scanner (rule_scanner.py): Deterministic substring, HTTP status & requested-phrase check
- Verifier (gemma4): Combines rule scan & screen text to report errors and save to SQLite
"""

import json
import logging
import re
from typing import Any, Dict, TypedDict

import ollama
from langgraph.graph import END, StateGraph

from browser_agent import LocalBrowserAgent
from database import ErrorCheckDatabase
from rule_scanner import format_rule_scan_summary, scan_page_rules

logger = logging.getLogger("ErrorCheckMultiAgent")

ROUTER_MODEL = "gemma2"
WORKER_MODEL = "gemma4"
DEFAULT_DEMO_URL = "http://localhost:5001/"


def _clean_url(raw_url: str) -> str:
    return raw_url.strip().strip("`\"'.,);]>")


class ErrorCheckState(TypedDict):
    user_query: str
    route: str
    inspection_plan: Dict[str, Any]
    inspection_result: Dict[str, Any]
    rule_scan: Dict[str, Any]
    verification_notes: str
    final_response: str


class LocalErrorCheckMultiAgent:
    def __init__(self, db: ErrorCheckDatabase, headless: bool = False) -> None:
        self.db = db
        self.browser = LocalBrowserAgent(headless=headless)
        self.graph = self._build_graph()

    def _chat(self, model: str, system_prompt: str, user_prompt: str) -> str:
        res = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.1},
        )
        return res["message"]["content"].strip()

    def _build_graph(self) -> Any:
        workflow = StateGraph(ErrorCheckState)

        workflow.add_node("router", self.node_router)
        workflow.add_node("inspector", self.node_inspector)
        workflow.add_node("rule_scanner", self.node_rule_scanner)
        workflow.add_node("verifier", self.node_verifier)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router",
            lambda s: s["route"],
            {
                "INSPECT_UI": "inspector",
                "GENERAL_HELP": "verifier",
            },
        )
        workflow.add_edge("inspector", "rule_scanner")
        workflow.add_edge("rule_scanner", "verifier")
        workflow.add_edge("verifier", END)

        return workflow.compile()

    def node_router(self, state: ErrorCheckState) -> Dict[str, Any]:
        q = state["user_query"]
        prompt = (
            "Classify the request into EXACTLY ONE label:\n"
            "- INSPECT_UI: Checking a webpage, URL, localhost app, form, or screen for errors or health status.\n"
            "- GENERAL_HELP: General question not requiring opening a browser.\n"
            "Return ONLY the label."
        )
        raw = self._chat(ROUTER_MODEL, prompt, q).upper()
        if "GENERAL_HELP" in raw and "http" not in q.lower() and "localhost" not in q.lower():
            route = "GENERAL_HELP"
        else:
            route = "INSPECT_UI"

        logger.info(f"[ROUTER - {ROUTER_MODEL}] -> {route}")
        return {"route": route}

    def node_inspector(self, state: ErrorCheckState) -> Dict[str, Any]:
        logger.info(f"[INSPECTOR - {WORKER_MODEL}] Planning & running browser inspection...")

        cleaned_query = state["user_query"].strip()
        if len(cleaned_query) >= 2 and cleaned_query[0] == cleaned_query[-1] and cleaned_query[0] in ('"', "'", "`"):
            cleaned_query = cleaned_query[1:-1].strip()

        plan_prompt = (
            "Convert the user request into a JSON inspection plan:\n"
            '{"url": "http://localhost:5001/", '
            '"field_actions": [{"selector": "#id", "value": "val"}] or [], '
            '"submit_selector": null or "#btn_id"}\n'
            "Rules:\n"
            "- Use the exact URL mentioned by the user (without backticks or quotes), or default to http://localhost:5001/.\n"
            "- Only include field_actions and submit_selector if the prompt asks to fill or submit a form.\n"
            "Return ONLY valid JSON."
        )
        raw_plan = self._chat(WORKER_MODEL, plan_prompt, cleaned_query)

        plan: Dict[str, Any] = {
            "url": DEFAULT_DEMO_URL,
            "field_actions": [],
            "submit_selector": None,
        }
        match = re.search(r"\{.*\}", raw_plan, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("url"), str) and parsed["url"].strip():
                        cleaned_parsed_url = _clean_url(parsed["url"])
                        if cleaned_parsed_url:
                            plan["url"] = cleaned_parsed_url
                    if isinstance(parsed.get("field_actions"), list):
                        plan["field_actions"] = [
                            {
                                "selector": str(item.get("selector", "")).strip(),
                                "value": "" if item.get("value") is None else str(item.get("value")),
                            }
                            for item in parsed["field_actions"]
                            if isinstance(item, dict) and str(item.get("selector", "")).strip()
                        ]
                    if isinstance(parsed.get("submit_selector"), str) and parsed["submit_selector"].strip():
                        plan["submit_selector"] = parsed["submit_selector"].strip()
            except json.JSONDecodeError as exc:
                logger.warning(f"[INSPECTOR] JSON parse warning: {exc} | raw={raw_plan!r}")

        # Always honor an explicit URL in the user's prompt, stripped of backticks/punctuation
        url_match = re.search(r"https?://[^\s\"'`]+", cleaned_query)
        if url_match:
            cleaned_explicit_url = _clean_url(url_match.group(0))
            if cleaned_explicit_url:
                plan["url"] = cleaned_explicit_url

        logger.info(f"[INSPECTOR] Plan: {json.dumps(plan)}")
        result = self.browser.inspect_page(
            url=plan["url"],
            field_actions=plan["field_actions"],
            submit_selector=plan["submit_selector"],
        )
        return {"inspection_plan": plan, "inspection_result": result}

    def node_rule_scanner(self, state: ErrorCheckState) -> Dict[str, Any]:
        logger.info("[RULE SCANNER] Running deterministic substring & HTTP status checks...")
        res = state.get("inspection_result") or {}
        scan = scan_page_rules(
            extracted_text=res.get("extracted_text", ""),
            http_status=res.get("http_status"),
            user_query=state["user_query"],
        )
        logger.info(f"[RULE SCANNER] {format_rule_scan_summary(scan)}")
        return {"rule_scan": scan}

    def node_verifier(self, state: ErrorCheckState) -> Dict[str, Any]:
        logger.info(f"[VERIFIER - {WORKER_MODEL}] Analyzing screen text & saving to SQLite...")
        res = state.get("inspection_result") or {}
        scan = state.get("rule_scan") or {}
        extracted = res.get("extracted_text", "")
        http_status = res.get("http_status")
        browser_err = res.get("error")
        rule_summary = format_rule_scan_summary(scan) if scan else "N/A"

        system_prompt = (
            "You are a UI error verification agent. Combine the deterministic rule scan "
            "with the visible page text and HTTP status. Treat phrases like 'Zero errors detected' "
            "or 'no errors' as healthy status—not as errors—unless an actual error message or "
            "HTTP >= 400 is present. Clearly state:\n"
            "1. Whether errors are present on screen (and quote any actual error messages found, or state 'No error').\n"
            "2. Exact status of any requested phrases (such as 'Out of memory').\n"
            "3. Whether the page is healthy or errored."
        )
        user_payload = (
            f"User Request: {state['user_query']}\n"
            f"Deterministic Rule Scan: {rule_summary}\n"
            f"Target URL: {res.get('final_url') or res.get('url') or 'N/A'}\n"
            f"Page Title: {res.get('title') or 'N/A'}\n"
            f"HTTP Status: {http_status if http_status is not None else 'N/A'}\n"
            f"Browser Error: {browser_err or 'None'}\n"
            f"Visible Screen Text:\n{extracted[:3500] if extracted else 'No text extracted.'}"
        )

        answer = self._chat(WORKER_MODEL, system_prompt, user_payload)
        matched_str = ",".join(scan.get("matched_rules") or []) or "none"
        notes = (
            f"Route={state['route']} | HTTP={http_status} | "
            f"Rules=[{matched_str}] | Err={browser_err or 'None'}"
        )

        if state["route"] == "INSPECT_UI":
            self.db.save_run(
                query=state["user_query"],
                target_url=res.get("final_url") or res.get("url") or "",
                page_title=res.get("title") or "",
                http_status=http_status,
                extracted_text=extracted[:2000],
                verification_notes=notes,
                status="FAILED" if browser_err else "COMPLETED",
            )

        return {"verification_notes": notes, "final_response": answer}

    def run(self, user_query: str) -> str:
        initial: ErrorCheckState = {
            "user_query": user_query,
            "route": "",
            "inspection_plan": {},
            "inspection_result": {},
            "rule_scan": {},
            "verification_notes": "",
            "final_response": "",
        }
        out = self.graph.invoke(initial)
        return out["final_response"]
