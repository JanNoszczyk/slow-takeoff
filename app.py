# --- Base Imports ---
from __future__ import annotations
import asyncio
import json
import logging
import os
import uuid
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, date
from enum import Enum
import httpx
from urllib.parse import urlencode
import random
from uuid import UUID

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from langchain_anthropic import ChatAnthropic
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel, Field, HttpUrl

# --- Imports from browser_use ---
try:
    from browser_use import Agent
    from browser_use.agent.views import AgentHistoryList
    from browser_use import BrowserConfig, Browser
except ImportError:
    print("Warning: 'browser-use' library not found. Browser automation features will fail.")
    Agent = None
    AgentHistoryList = None
    BrowserConfig = None
    Browser = None

# --- Load Environment Variables ---
load_dotenv()

# --- Logging Configuration ---
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("combined-app")

# --- FastAPI App Initialization ---
app = FastAPI(title="Combined Browser Bridge, Gateway, and Mock API")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Browser Bridge Section ===

class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    STOPPED = "stopped"
    PAUSED = "paused"
    FAILED = "failed"
    STOPPING = "stopping"

tasks: Dict[str, Dict] = {}

class TaskRequest(BaseModel):
    task: str
    ai_provider: Optional[str] = "openai"
    save_browser_data: Optional[bool] = False
    headful: Optional[bool] = None
    use_custom_chrome: Optional[bool] = None

class TaskResponse(BaseModel):
    id: str
    status: str
    live_url: str

class TaskStatusResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None

def get_llm(ai_provider: str):
    # Simplified get_llm logic
    if ai_provider == "anthropic": return ChatAnthropic(model=os.environ.get("ANTHROPIC_MODEL_ID", "claude-3-opus-20240229"))
    if ai_provider == "mistral": return ChatMistralAI(model=os.environ.get("MISTRAL_MODEL_ID", "mistral-large-latest"))
    if ai_provider == "google": return ChatGoogleGenerativeAI(model=os.environ.get("GOOGLE_MODEL_ID", "gemini-1.5-pro"))
    if ai_provider == "ollama": return ChatOllama(model=os.environ.get("OLLAMA_MODEL_ID", "llama3"))
    if ai_provider == "azure": return AzureChatOpenAI(azure_deployment=os.environ.get("AZURE_DEPLOYMENT_NAME"), openai_api_version=os.environ.get("AZURE_API_VERSION", "2023-05-15"), azure_endpoint=os.environ.get("AZURE_ENDPOINT"))
    base_url = os.environ.get("OPENAI_BASE_URL"); kwargs = {"model": os.environ.get("OPENAI_MODEL_ID", "gpt-4o")};
    if base_url: kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)

async def execute_task(task_id: str, instruction: str, ai_provider: str):
    if Agent is None or Browser is None or BrowserConfig is None:
        logger.error(f"browser-use library not loaded, cannot execute task {task_id}"); tasks[task_id].update({"status": TaskStatus.FAILED, "error": "browser-use library not available", "finished_at": datetime.utcnow().isoformat() + "Z"}); return
    browser = None
    try:
        tasks[task_id]["status"] = TaskStatus.RUNNING; llm = get_llm(ai_provider); task_browser_config = tasks[task_id].get("browser_config", {}); task_headful = task_browser_config.get("headful")
        if task_headful is not None: headful = task_headful
        else: headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"
        use_custom_chrome = task_browser_config.get("use_custom_chrome")
        if use_custom_chrome is False: chrome_path, chrome_user_data = None, None
        else: chrome_path, chrome_user_data = os.environ.get("CHROME_PATH"), os.environ.get("CHROME_USER_DATA")
        agent_kwargs = {"task": instruction, "llm": llm}
        if not headful or chrome_path or chrome_user_data:
            extra_chromium_args = []; browser_config_args = {"headless": not headful}
            if not headful: extra_chromium_args += ["--headless=new"]
            if chrome_path: browser_config_args["chrome_instance_path"] = chrome_path
            if chrome_user_data: extra_chromium_args += [f"--user-data-dir={chrome_user_data}"]
            if extra_chromium_args: browser_config_args["extra_chromium_args"] = extra_chromium_args
            logger.info(f"Task {task_id}: Browser config args: {browser_config_args}"); browser_config = BrowserConfig(**browser_config_args); browser = Browser(config=browser_config); agent_kwargs["browser"] = browser
        logger.info(f"Task {task_id}: Agent kwargs prepared."); agent = Agent(**agent_kwargs); tasks[task_id]["agent"] = agent
        async def step_callback(step_data): step_id = str(uuid.uuid4()); step_num = len(tasks[task_id]["steps"]) + 1; step = {"id": step_id, "step": step_num, "evaluation_previous_goal": step_data.get("evaluation", ""), "next_goal": step_data.get("goal", "")}; tasks[task_id]["steps"].append(step)
        if hasattr(agent, "add_callback"): agent.add_callback("on_step", step_callback)
        result = await agent.run(); tasks[task_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"; tasks[task_id]["status"] = TaskStatus.FINISHED
        if isinstance(result, AgentHistoryList): tasks[task_id]["output"] = result.final_result()
        else: tasks[task_id]["output"] = str(result)
        if tasks[task_id]["save_browser_data"] and hasattr(agent, "browser"):
            try: # Corrected try...except
                cookies = [];
                if hasattr(agent.browser, "get_cookies"): cookies = await agent.browser.get_cookies()
                elif hasattr(agent.browser, "page") and hasattr(agent.browser.page, "cookies"): cookies = await agent.browser.page.cookies()
                elif hasattr(agent.browser, "context") and hasattr(agent.browser.context, "cookies"): cookies = await agent.browser.context.cookies()
                else: logger.warning(f"No known method to collect cookies for task {task_id}")
                tasks[task_id]["browser_data"] = {"cookies": cookies}
            except Exception as e: logger.error(f"Failed to collect browser data: {str(e)}"); tasks[task_id]["browser_data"] = {"cookies": [], "error": str(e)}
    except Exception as e: logger.exception(f"Error executing task {task_id}"); tasks[task_id].update({"status": TaskStatus.FAILED, "error": str(e), "finished_at": datetime.utcnow().isoformat() + "Z"})
    finally:
        if browser is not None:
            logger.info(f"Closing browser for task {task_id}")
            try:
                await browser.close()
            except Exception as e:
                logger.error(f"Error closing browser for task {task_id}: {str(e)}")

bridge_router = APIRouter(prefix="/api/v1", tags=["Browser Bridge"])

@bridge_router.post("/run-task", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    live_url = f"/live/{task_id}"
    tasks[task_id] = {
        "id": task_id,
        "task": request.task,
        "ai_provider": request.ai_provider,
        "status": TaskStatus.CREATED,
        "created_at": now,
        "finished_at": None,
        "output": None,
        "error": None,
        "steps": [],
        "agent": None,
        "save_browser_data": request.save_browser_data,
        "browser_data": None,
        "live_url": live_url,
        "browser_config": {
            "headful": request.headful,
            "use_custom_chrome": request.use_custom_chrome
        }
    }
    asyncio.create_task(execute_task(task_id, request.task, request.ai_provider))
    return TaskResponse(id=task_id, status=TaskStatus.CREATED, live_url=live_url)

@bridge_router.get("/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(
        status=tasks[task_id]["status"],
        result=tasks[task_id].get("output"),
        error=tasks[task_id].get("error")
    ) # Removed jsonable_encoder, return Pydantic model directly

@bridge_router.get("/task/{task_id}", response_model=dict)
async def get_task(task_id: str):
    """Retrieves details for a specific task, excluding the agent object."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task_data = {k: v for k, v in tasks[task_id].items() if k != "agent"}
    # Enums might not be automatically encoded by default dict response_model
    # Let FastAPI handle it if possible, otherwise use jsonable_encoder if needed
    # For now, returning raw dict. Test if Enums serialize correctly.
    return task_data

@bridge_router.put("/stop-task/{task_id}")
async def stop_task(task_id: str):
    """Stops a running or stopping task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    if tasks[task_id]["status"] in [TaskStatus.FINISHED, TaskStatus.FAILED, TaskStatus.STOPPED]:
        return {"message": f"Task already in terminal state: {tasks[task_id]['status']}"}

    agent = tasks[task_id].get("agent")
    if agent and hasattr(agent, 'stop'):
        try:
            agent.stop() # Assuming this is synchronous or handled appropriately by browser-use
        except Exception as e:
            logger.warning(f"Error calling agent.stop(): {e}")
        # Even if stop fails, mark as stopping/stopped
        tasks[task_id]["status"] = TaskStatus.STOPPING
        # Ideally, agent.stop() would trigger a status update later, but for now:
        # If agent.stop() is async, this might need adjustment.
        # Simpler: Mark as stopping and let polling/callback handle final STOPPED state.
        return {"message": "Task stopping signal sent"}
    else:
        # If no agent or stop method, force stop
        tasks[task_id].update({
            "status": TaskStatus.STOPPED,
            "finished_at": datetime.utcnow().isoformat() + "Z"
        })
        return {"message": "Task stopped (no agent/stop method or already stopped)"}

@bridge_router.put("/pause-task/{task_id}")
async def pause_task(task_id: str):
    """Pauses a running task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    if tasks[task_id]["status"] != TaskStatus.RUNNING:
        return {"message": f"Task not running: {tasks[task_id]['status']}"}

    agent = tasks[task_id].get("agent")
    if agent and hasattr(agent, 'pause'):
        try:
            agent.pause() # Assuming synchronous pause
        except Exception as e:
            logger.warning(f"Error calling agent.pause(): {e}")
            # Proceed to set status even if pause call fails? Or return error?
            # For now, assume pause worked if method exists
        tasks[task_id]["status"] = TaskStatus.PAUSED
        return {"message": "Task paused"}
    else:
        return {"message": "Task could not be paused (no agent or pause method)"}

@bridge_router.put("/resume-task/{task_id}")
async def resume_task(task_id: str):
    """Resumes a paused task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    if tasks[task_id]["status"] != TaskStatus.PAUSED:
        return {"message": f"Task not paused: {tasks[task_id]['status']}"}

    agent = tasks[task_id].get("agent")
    if agent and hasattr(agent, 'resume'):
        try:
            agent.resume() # Assuming synchronous resume
        except Exception as e:
            logger.warning(f"Error calling agent.resume(): {e}")
            # Proceed to set status even if resume call fails?
        tasks[task_id]["status"] = TaskStatus.RUNNING
        return {"message": "Task resumed"}
    else:
        return {"message": "Task could not be resumed (no agent or resume method)"}

@bridge_router.get("/list-tasks", response_model=dict) # Using dict for simplicity, define a model if stricter validation needed
async def list_tasks():
    """Lists summaries of all tasks."""
    task_list = []
    for task_id, task_data in tasks.items():
        task_summary = {
            k: v for k, v in task_data.items()
            if k in ["id", "status", "task", "created_at", "finished_at", "live_url"]
        }
        # Manually convert Enum to string for JSON compatibility if needed
        if isinstance(task_summary.get("status"), Enum):
             task_summary["status"] = task_summary["status"].value
        task_list.append(task_summary)

    # Returning a simple dict structure, matches previous jsonable_encoder output
    return {
        "tasks": task_list,
        "total": len(task_list),
        "page": 1, # Assuming no pagination for now
        "per_page": len(tasks)
    }

@bridge_router.get("/ping")
async def ping(): return {"status": "success", "message": "Browser Bridge API is running"}
@bridge_router.get("/browser-config")
async def browser_config(): headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"; chrome_path = os.environ.get("CHROME_PATH"); chrome_user_data = os.environ.get("CHROME_USER_DATA"); return {"headful": headful, "headless": not headful, "chrome_path": chrome_path, "chrome_user_data": chrome_user_data, "using_custom_chrome": chrome_path is not None, "using_user_data": chrome_user_data is not None}

@app.get("/live/{task_id}", response_class=HTMLResponse, tags=["Browser Bridge"])
async def live_view(task_id: str, request: Request):
    if task_id not in tasks: raise HTTPException(status_code=404, detail="Task not found")
    base_api_path = str(request.base_url).rstrip('/') + "/api/v1"
    # HTML with corrected JS and CSS class names
    html_content = f"""
    <!DOCTYPE html><html><head><title>Task {task_id}</title><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:sans-serif;margin:20px;}}.status{{padding:10px;border-radius:4px;margin-bottom:20px;}}.controls{{margin-bottom:20px;}}button{{padding:8px 16px;margin-right:10px;cursor:pointer;}}pre{{background-color:#f5f5f5;padding:15px;border-radius:4px;overflow:auto;}}.step{{margin-bottom:10px;padding:10px;border:1px solid #ddd;border-radius:4px;}}
    .status.{TaskStatus.RUNNING.value}{{background-color:#e3f2fd;}} .status.{TaskStatus.FINISHED.value}{{background-color:#e8f5e9;}} .status.{TaskStatus.FAILED.value}{{background-color:#ffebee;}}
    .status.{TaskStatus.PAUSED.value}{{background-color:#fff8e1;}} .status.{TaskStatus.STOPPED.value}{{background-color:#eeeeee;}} .status.{TaskStatus.CREATED.value}{{background-color:#f3e5f5;}} .status.{TaskStatus.STOPPING.value}{{background-color:#fce4ec;}}</style>
    </head><body><div class="container"><h1>Task Live View</h1><div id="status" class="status">Loading...</div>
    <div class="controls"><button id="pauseBtn">Pause</button><button id="resumeBtn">Resume</button><button id="stopBtn">Stop</button></div>
    <h2>Result</h2><pre id="result">Loading...</pre><h2>Steps</h2><div id="steps">Loading...</div>
    <script>
        const taskId = '{task_id}'; const baseApi = '{base_api_path}'; const FINISHED = '{TaskStatus.FINISHED.value}'; const FAILED = '{TaskStatus.FAILED.value}'; const STOPPED = '{TaskStatus.STOPPED.value}';
        function updateStatus() {{
            fetch(baseApi + '/task/' + taskId + '/status').then(r=>r.json()).then(d=>{{ const s=document.getElementById('status'); s.textContent='Status: '+d.status; s.className='status '+d.status; if(d.result){{document.getElementById('result').textContent=d.result;}}else if(d.error){{document.getElementById('result').textContent='Error: '+d.error;}} }}).catch(e=>console.error('Status fetch error:',e));
            fetch(baseApi + '/task/' + taskId).then(r=>r.json()).then(d=>{{ if(d.steps&&d.steps.length>0){{ const h=d.steps.map(s=>'<div class="step"><strong>Step '+s.step+'</strong><p>Goal: '+(s.next_goal||'N/A')+'</p><p>Eval: '+(s.evaluation_previous_goal||'N/A')+'</p></div>').join(''); document.getElementById('steps').innerHTML=h; }}else{{ document.getElementById('steps').textContent='No steps yet.'; }} }}).catch(e=>console.error('Task details fetch error:',e));
        }}
        document.getElementById('pauseBtn').addEventListener('click',()=>{{ fetch(baseApi + '/pause-task/' + taskId,{{method:'PUT'}}).then(r=>r.json()).then(d=>alert(d.message)).catch(e=>console.error('Pause error:',e)); updateStatus(); }});
        document.getElementById('resumeBtn').addEventListener('click',()=>{{ fetch(baseApi + '/resume-task/' + taskId,{{method:'PUT'}}).then(r=>r.json()).then(d=>alert(d.message)).catch(e=>console.error('Resume error:',e)); updateStatus(); }});
        document.getElementById('stopBtn').addEventListener('click',()=>{{ if(confirm('Stop task?')){{ fetch(baseApi + '/stop-task/' + taskId,{{method:'PUT'}}).then(r=>r.json()).then(d=>alert(d.message)).catch(e=>console.error('Stop error:',e)); updateStatus(); }} }});
        updateStatus(); setInterval(updateStatus, 5000);
    </script></div></body></html>"""
    return HTMLResponse(content=html_content)

# === OData Gateway Section ===

gateway_router = APIRouter(prefix="/gateway", tags=["OData Gateway"])
VIDAR_BASE_URL = os.getenv("VIDAR_BASE_URL")
VIDAR_API_KEY = os.getenv("VIDAR_API_KEY")

@gateway_router.get("/myodata/{entity_set:path}", summary="Forward OData GET Request")
async def forward_odata_request(entity_set: str, request: Request):
    if not VIDAR_BASE_URL or not VIDAR_API_KEY: raise HTTPException(status_code=503, detail="Gateway backend service not configured (VIDAR_BASE_URL/VIDAR_API_KEY missing).")
    _vidar_base_url = VIDAR_BASE_URL[:-1] if VIDAR_BASE_URL.endswith('/') else VIDAR_BASE_URL
    backend_path = f"/v1/{entity_set}"; query_string = urlencode(request.query_params); backend_url = f"{_vidar_base_url}{backend_path}"
    if query_string: backend_url += f"?{query_string}"
    headers = {"x-api-key": VIDAR_API_KEY, "Accept": request.headers.get("Accept", "application/json")}
    async with httpx.AsyncClient() as client:
        try: logger.info(f"Gateway forwarding request to: {backend_url}"); response = await client.get(backend_url, headers=headers, follow_redirects=True); response_headers = {k: v for k, v in response.headers.items() if k.lower() in ['content-type', 'odata-version', 'content-language']}; return Response(content=response.content, status_code=response.status_code, headers=response_headers)
        except httpx.RequestError as exc: logger.error(f"Gateway error requesting {exc.request.url!r}: {exc}"); raise HTTPException(status_code=502, detail=f"Bad Gateway: {exc}")
        except Exception as exc: logger.error(f"Gateway unexpected error: {exc}"); raise HTTPException(status_code=500, detail=f"Internal Server Error: {exc}")

@gateway_router.get("/ping", summary="Gateway Health Check")
async def gateway_ping(): return {"status": "OData Gateway is running"}

# === Mock Vidar API Section ===

mock_router = APIRouter(prefix="/mock_api/v1", tags=["Mock Vidar API"])

# --- Pydantic Models based on components.json ---

# Enums
class MandateType(str, Enum):
    ADVISORY = "Advisory"
    DISCRETIONARY = "Discretionary"
    EXECUTION_ONLY = "ExecutionOnly"
    OFF_MANAGEMENT = "OffManagement"
    READ_ONLY = "ReadOnly"

class PortfolioType(str, Enum):
    CLIENT = "Client"
    MODEL = "Model"
    NON_FINANCIAL = "NonFinancial"
    CONSOLIDATED = "Consolidated"
    EXTERNAL = "External"
    FUND = "Fund"
    BENCHMARK = "Benchmark"
    SUBACCOUNT = "Subaccount"

class TransactionType(str, Enum):
    UNCLASSIFIED = "Unclassified"
    BUY = "Buy"
    SELL = "Sell"
    INCOME = "Income"
    FX_TRADE = "FxTrade"
    FEES = "Fees"
    DEPOSIT_WITHDRAWAL = "DepositWithdrawal"
    TAX = "Tax"
    SUBSCRIPTION = "Subscription"
    REDEMPTION = "Redemption"
    OPERATIONAL_FEES = "OperationalFees"
    CORPORATE_ACTION = "CorporateAction"
    INTERNAL_TRANSFER = "InternalTransfer"
    OTHER = "Other"
    ASSET_TRANSFER = "AssetTransfer"
    EXPENSE = "Expense"
    OPEN_DEPOSIT = "OpenDeposit"
    CLOSE_DEPOSIT = "CloseDeposit"
    EXPIRY = "Expiry"
    CALL = "Call"
    CONVERSION = "Conversion"
    WITHHOLDING_TAX = "WithholdingTax"
    INTEREST = "Interest"
    DIVIDEND = "Dividend"
    COUPON = "Coupon"
    BANK_FEE = "BankFee"
    MANAGEMENT_FEE = "ManagementFee"
    PERFORMANCE_FEE = "PerformanceFee"
    OPEN_LOAN = "OpenLoan"
    CLOSE_LOAN = "CloseLoan"
    FX_SPOT = "FxSpot"
    EXCHANGE = "Exchange"
    MERGER = "Merger"
    SPLIT = "Split"
    SPIN_OFF = "SpinOff"
    CASH_IN_LIEU = "CashInLieu"
    FX_FORWARD = "FxForward"
    CANCELLATION = "Cancellation"
    COMMISSION = "Commission"
    STAMP_DUTY = "StampDuty"
    MARGIN_PAYMENT = "MarginPayment"
    ASSIMILATION = "Assimilation"
    BONUS_ISSUE = "BonusIssue"
    CAPITAL_DECREASE = "CapitalDecrease"
    CAPITAL_INCREASE = "CapitalIncrease"
    DELISTING = "Delisting"
    NAME_CHANGE = "NameChange"
    PARTIAL_REDEMPTION = "PartialRedemption"
    REVERSE_SPLIT = "ReverseSplit"
    OPEN_LONG_POSITION = "OpenLongPosition"
    OPEN_SHORT_POSITION = "OpenShortPosition"

# --- Base Models ---
class Asset(BaseModel):
    id: int
    name: Optional[str] = None
    currency: Optional[str] = None
    assetClass: Optional[str] = None
    assetSubClass: Optional[str] = None
    investmentType: Optional[str] = None
    description: Optional[str] = None
    quotationFactor: Optional[float] = None
    interestRate: Optional[float] = None
    maturityDate: Optional[date] = None
    riskScore: Optional[int] = Field(None, ge=1, le=10)

class CashAccount(Asset):
    iban: Optional[str] = None
    odata_type: str = Field("#WealthArc.CashAccount", alias="@odata.type", exclude=True) # Exclude from model dump but use for type checking

class Instrument(Asset):
    isin: Optional[str] = None
    valor: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None
    industryGroup: Optional[str] = None
    industry: Optional[str] = None
    subIndustry: Optional[str] = None
    instrumentInfo: Optional[str] = None
    wkn: Optional[str] = None
    cusip: Optional[str] = None
    sedol: Optional[str] = None
    ric: Optional[str] = None
    figi: Optional[str] = None
    optionType: Optional[str] = None
    underlyingInstrument: Optional[str] = None
    underlyingInstrumentIsin: Optional[str] = None
    strikePrice: Optional[float] = None
    multiplier: Optional[float] = None
    instrumentIssuer: Optional[str] = None
    suitabilityScore: Optional[int] = None
    appropriatenessScore: Optional[int] = None
    priceSourceForManualPortfolio: Optional[str] = None
    odata_type: str = Field("#WealthArc.Instrument", alias="@odata.type", exclude=True)

AnyAsset = Union[CashAccount, Instrument] # For use in responses

class Portfolio(BaseModel):
    id: int
    name: Optional[str] = None
    shortName: Optional[str] = None
    custodianId: Optional[str] = None
    custodian: Optional[str] = None
    currency: Optional[str] = None
    wealthArcCurrency: Optional[str] = None
    description: Optional[str] = None
    additionalInfo: Optional[str] = None
    isActive: Optional[bool] = None
    inceptionDate: Optional[date] = None
    endDate: Optional[date] = None
    relationshipManager: Optional[str] = None
    portfolioManager: Optional[str] = None
    assistant: Optional[str] = None
    branch: Optional[str] = None
    profitCenter: Optional[str] = None
    parentPortfolioId: Optional[int] = None
    investmentGroup: Optional[str] = None
    modelPortfolioId: Optional[int] = None
    mandateType: Optional[MandateType] = None
    isManual: Optional[bool] = None
    type: Optional[PortfolioType] = None # Schema implies required, but Optional okay for flexibility

class PositionValue(BaseModel):
    id: int # Corrected: Schema implies required
    positionId: int # Corrected: Schema implies required
    amount: Optional[float] = None
    currency: Optional[str] = None
    fxRateDate: Optional[datetime] = None # Using datetime reflects schema format
    fxRateFrom: Optional[str] = None
    fxRateTo: Optional[str] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None

class PositionPnl(BaseModel):
    positionId: int # Corrected: Schema implies required
    # portfolioId: Optional[int] = None # REMOVED - Not in schema definition
    totalPnL: Optional[float] = None
    totalPnLPercentage: Optional[float] = None
    marketPnL: Optional[float] = None
    marketPnLPercentage: Optional[float] = None
    pnLCurrencyEffect: Optional[float] = None
    totalPnLWithCashflow: Optional[float] = None
    totalPnLWithCashflowPercentage: Optional[float] = None
    cumulativeCashflow: Optional[float] = None

# Only one definition now, used for Position and PortfolioDailyMetrics
class PositionPerformance(BaseModel):
    positionId: int # Corrected: Schema implies required
    # NOTE: Schema shows this model under Position, but PortfolioDailyMetrics also references it.
    # The properties below match the schema for PositionPerformance.
    ytdMarket: Optional[float] = None
    mtdMarket: Optional[float] = None
    ytdCurrencyEffect: Optional[float] = None
    mtdCurrencyEffect: Optional[float] = None
    ytdPerformance: Optional[float] = None
    mtdPerformance: Optional[float] = None
    # The following fields were specific to the DailyMetrics version and seem redundant/mistakenly duplicated
    # statementDate: date # This is in PortfolioDailyMetrics level
    # ytdCalculationStartDate: Optional[date] = None # This is in PortfolioDailyMetrics level
    # ytdGross: Optional[float] = None # This is in PortfolioDailyMetrics level
    # ytdNet: Optional[float] = None # This is in PortfolioDailyMetrics level
    # mtdGross: Optional[float] = None # This is in PortfolioDailyMetrics level
    # mtdNet: Optional[float] = None # This is in PortfolioDailyMetrics level


class Position(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    assetId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    quantity: float # Corrected: Schema implies required
    price: Optional[float] = None # Optional, matches schema
    priceCurrency: Optional[str] = None # Optional, matches schema
    valueDate: Optional[date] = None
    priceSource: Optional[str] = None
    unitCostInPriceCurrency: Optional[float] = None
    allocation: Optional[float] = None
    portfolioCurrency: Optional[str] = None
    bookCostInPortfolioCurrency: Optional[float] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None
    accruedInterestInPriceCurrency: Optional[float] = None
    accruedInterestInPortfolioCurrency: Optional[float] = None
    cumulativeCashflowInPriceCurrency: Optional[float] = None
    values: Optional[List[PositionValue]] = None # Structure matches, uses corrected PositionValue
    pnl: Optional[List[PositionPnl]] = None # Structure matches, uses corrected PositionPnl
    performances: Optional[List[PositionPerformance]] = None # Structure matches, uses corrected PositionPerformance

class TransactionValue(BaseModel):
    id: UUID # Corrected: Schema implies required UUID
    transactionId: int # Corrected: Schema implies required int
    amount: Optional[float] = None # Optional, matches schema
    currency: Optional[str] = None # Optional, matches schema
    fxRateDate: Optional[datetime] = None # Using datetime reflects schema format
    fxRateFrom: Optional[str] = None
    fxRateTo: Optional[str] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None

class Transaction(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    assetId: int # Corrected: Schema implies required
    type: TransactionType # Corrected: Schema implies required
    description: Optional[str] = None # Optional, matches schema
    transactionDate: date # Required, matches schema
    tradeDate: Optional[date] = None
    valueDate: Optional[date] = None
    quantity: Optional[float] = None # Optional, matches schema
    price: Optional[float] = None # Optional, matches schema
    priceCurrency: Optional[str] = None # Optional, matches schema
    portfolioCurrency: Optional[str] = None # Optional, matches schema
    fxRate: Optional[float] = None # Optional, matches schema
    fxRateSource: Optional[str] = None # Optional, matches schema
    externalOrderId: Optional[str] = None # Optional, matches schema
    referencedInstrumentId: Optional[int] = None # Optional, matches schema
    referencedInstrumentQuantity: Optional[float] = None # Optional, matches schema
    interest: Optional[float] = None # Optional, matches schema
    isReversal: Optional[bool] = None # Optional, matches schema
    isRiskIncreased: Optional[bool] = None # Optional, matches schema
    values: Optional[List[TransactionValue]] = None # Structure matches, uses corrected TransactionValue


# --- Models related to PortfolioDailyMetrics ---

# ADDED MISSING MODEL based on schema
class CustodianPortfolioPerformance(BaseModel):
    portfolioId: int # Schema implies required
    statementDate: date # Required
    portfolioCurrency: Optional[str] = None # Optional, matches schema
    ytdCalculationStartDate: Optional[date] = None
    ytdGross: Optional[float] = None
    ytdNet: Optional[float] = None
    mtdGross: Optional[float] = None
    mtdNet: Optional[float] = None

class PortfolioAum(BaseModel):
    portfolioDailyMetricsId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    netAmount: float # Corrected: Schema implies required
    grossAmount: float # Corrected: Schema implies required
    currency: Optional[str] = None # Optional, matches schema

# REMOVED DUPLICATE/SECOND Definition of PortfolioPerformance

# Corrected PortfolioDailyMetrics (single definition)
class PortfolioDailyMetrics(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    overdraftsCount: Optional[int] = None # Optional, matches schema
    custodianPerformances: Optional[List[CustodianPortfolioPerformance]] = None # Structure matches, uses added CustodianPortfolioPerformance
    aums: Optional[List[PortfolioAum]] = None # Structure matches, uses corrected PortfolioAum
    performances: Optional[List[PositionPerformance]] = None # Structure matches, uses corrected PositionPerformance


# --- OData Response Models (Seem correct, rely on corrected base models) ---
class ODataResponseBase(BaseModel):
    context: Optional[str] = Field(None, alias="@odata.context")
    count: Optional[int] = Field(None, alias="@odata.count")

class AssetODataCollectionResponse(ODataResponseBase):
    value: Optional[List[AnyAsset]] = None # Handles CashAccount or Instrument

class AssetODataResponse(ODataResponseBase):
    value: Optional[AnyAsset] = None

class CashAccountODataCollectionResponse(ODataResponseBase):
    value: Optional[List[CashAccount]] = None

class InstrumentODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Instrument]] = None

class PortfolioODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Portfolio]] = None

class PortfolioODataResponse(ODataResponseBase):
    value: Optional[Portfolio] = None

class PositionODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Position]] = None

class PositionODataResponse(ODataResponseBase):
    value: Optional[Position] = None

class TransactionODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Transaction]] = None

class TransactionODataResponse(ODataResponseBase):
    value: Optional[Transaction] = None

class PortfolioDailyMetricsODataCollectionResponse(ODataResponseBase):
    value: Optional[List[PortfolioDailyMetrics]] = None

class PortfolioDailyMetricsODataResponse(ODataResponseBase):
    value: Optional[PortfolioDailyMetrics] = None

# --- Mock Helper Functions ---
def get_odata_context(request: Request, entity_set: str, is_entity: bool = False) -> str:
    base = str(request.base_url).rstrip('/') + "/mock_api/v1/$metadata#" + entity_set
    return base + "/$entity" if is_entity else base

# --- Mock Data (Examples conforming to Pydantic Models) ---
# Using example values from components.json where available
# NOTE: Mock data updated to conform to the corrected required fields where possible

EXAMPLE_ASSETS: List[AnyAsset] = [
    CashAccount(id=25237, name="Example Cash Account", currency="USD", assetClass="Deposits, Money Market and Fixed Income", assetSubClass="Cash", investmentType="Loan", description="Sample Description", quotationFactor=1.0, interestRate=1.3, maturityDate=date(2018, 3, 2), riskScore=3, iban="CH5604835012345678009", odata_type="#WealthArc.CashAccount"),
    Instrument(id=25238, name="Example Instrument", currency="CHF", assetClass="Equities", assetSubClass="Stocks", investmentType="Stock", isin="US46434G8226", valor="034388865", region="CH", country="CH", sector="Financials", riskScore=7, odata_type="#WealthArc.Instrument")
]

EXAMPLE_PORTFOLIOS: List[Portfolio] = [
    Portfolio(id=30825, name="Yann Sommer", shortName="Yann S.", custodianId="500273.43", custodian="LODH", currency="EUR", wealthArcCurrency="CHF", description="Equity portfolio", isActive=True, inceptionDate=date(2024, 1, 26), relationshipManager="David Gasser", mandateType=MandateType.ADVISORY, type=PortfolioType.CLIENT),
    Portfolio(id=30826, name="Test Portfolio", currency="CHF", wealthArcCurrency="CHF", isActive=True, inceptionDate=date(2023, 1, 1), isManual=True, type=PortfolioType.MODEL)
]

# Corrected EXAMPLE_POSITIONS: Ensure required fields have values
# Added dummy IDs for PositionValue where schema implies required
EXAMPLE_POSITIONS: List[Position] = [
    Position(id=601345, portfolioId=30825, assetId=25238, statementDate=date(2024, 1, 26), quantity=50.0, price=1869.0, priceCurrency="USD", valueDate=date(2024, 1, 26), priceSource="LODH", allocation=0.1321, portfolioCurrency="EUR", bookCostInPortfolioCurrency=48499.16, fxRate=0.9561, values=[PositionValue(id=1, positionId=601345, amount=93450.0, currency="USD"), PositionValue(id=2, positionId=601345, amount=89351.68, currency="EUR")], pnl=[PositionPnl(positionId=601345, totalPnL=46023.64, totalPnLPercentage=0.9489)], performances=[PositionPerformance(positionId=601345, ytdPerformance=-0.0114)]),
    Position(id=601346, portfolioId=30826, assetId=25237, statementDate=date(2024, 1, 26), quantity=10000.0, price=1.0, priceCurrency="CHF", valueDate=date(2024, 1, 26), priceSource="MANUAL", allocation=0.04, portfolioCurrency="CHF", bookCostInPortfolioCurrency=10000.0, values=[PositionValue(id=3, positionId=601346, amount=10000.0, currency="CHF")])
]

# Corrected EXAMPLE_TRANSACTIONS: Ensure required fields have values
# Generating UUIDs for TransactionValue id
EXAMPLE_TRANSACTIONS: List[Transaction] = [
    Transaction(id=701345, portfolioId=30825, assetId=25238, type=TransactionType.BUY, description="Stock transaction", transactionDate=date(2018, 8, 21), tradeDate=date(2018, 8, 21), valueDate=date(2018, 8, 21), quantity=10.0, price=145.844, priceCurrency="USD", portfolioCurrency="EUR", fxRate=0.8681, externalOrderId="41REF.9730137", values=[TransactionValue(id=uuid.uuid4(), transactionId=701345, amount=-1458.44, currency="USD"), TransactionValue(id=uuid.uuid4(), transactionId=701345, amount=-1266.15, currency="EUR")]),
    Transaction(id=701346, portfolioId=30826, assetId=25237, type=TransactionType.DEPOSIT_WITHDRAWAL, transactionDate=date(2024, 1, 5), quantity=5000.0, price=1.0, priceCurrency="CHF", portfolioCurrency="CHF", values=[TransactionValue(id=uuid.uuid4(), transactionId=701346, amount=5000.0, currency="CHF")])
]

# Corrected EXAMPLE_PORTFOLIO_DAILY_METRICS: Ensure required fields have values
EXAMPLE_PORTFOLIO_DAILY_METRICS: List[PortfolioDailyMetrics] = [
    PortfolioDailyMetrics(id=301246, portfolioId=30825, statementDate=date(2024, 1, 26), overdraftsCount=1, aums=[PortfolioAum(portfolioDailyMetricsId=301246, statementDate=date(2024, 1, 26), netAmount=3277457.8, grossAmount=3277457.8, currency="CHF")], custodianPerformances=[CustodianPortfolioPerformance(portfolioId=30825, statementDate=date(2024, 1, 26), ytdGross=-0.0061)], performances=[PositionPerformance(positionId=601345, ytdMarket=-0.00612063, mtdMarket=-0.00532612)]), # Using PositionPerformance fields for example
    PortfolioDailyMetrics(id=301247, portfolioId=30826, statementDate=date(2024, 1, 26), aums=[PortfolioAum(portfolioDailyMetricsId=301247, statementDate=date(2024, 1, 26), netAmount=10000.0, grossAmount=10000.0, currency="CHF")])
]


# --- Mock Endpoints Implementation ---
@mock_router.get("/$metadata")
async def get_mock_metadata():
    # Placeholder for actual XML metadata generation if needed
    return Response(content="<xml>Mock Metadata placeholder</xml>", media_type="application/xml")

# Assets
@mock_router.get("/Assets", response_model=AssetODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_assets(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    # Simplified: Ignores filter/select/top/skip/orderby, returns all examples
    logger.info(f"GET /mock_api/v1/Assets | Params: {req.query_params} (ignored)")
    response_data = {
        "@odata.context": get_odata_context(req, "Assets"),
        "value": EXAMPLE_ASSETS
    }
    if cnt:
        response_data["@odata.count"] = len(EXAMPLE_ASSETS)
    return response_data # Removed jsonable_encoder

@mock_router.get("/Assets/{key}", response_model=AssetODataResponse, response_model_exclude_unset=True)
async def get_mock_asset_by_key(key: int, req: Request):
    # Simplified: Ignores select, finds by key
    logger.info(f"GET /mock_api/v1/Assets/{key} | Params: {req.query_params} (ignored)")
    asset = next((a for a in EXAMPLE_ASSETS if a.id == key), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Mock Asset not found")
    # Manually add odata.type for single entity response based on instance type
    if isinstance(asset, CashAccount):
        value_dict = asset.model_dump(by_alias=True, exclude_unset=True)
        value_dict["@odata.type"] = "#WealthArc.CashAccount"
    elif isinstance(asset, Instrument):
        value_dict = asset.model_dump(by_alias=True, exclude_unset=True)
        value_dict["@odata.type"] = "#WealthArc.Instrument"
    else:
        value_dict = asset.model_dump(by_alias=True, exclude_unset=True) # Fallback

    response_data = {
        "@odata.context": get_odata_context(req, "Assets", is_entity=True),
        "value": value_dict
    }
    return response_data # Removed jsonable_encoder

@mock_router.get("/Assets/WealthArc.CashAccount", response_model=CashAccountODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_cash_accounts(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/Assets/WealthArc.CashAccount | Params: {req.query_params} (ignored)")
    cash_accounts = [a for a in EXAMPLE_ASSETS if isinstance(a, CashAccount)]
    response_data = {
        "@odata.context": get_odata_context(req, "Assets/WealthArc.CashAccount"),
        "value": cash_accounts
    }
    if cnt:
        response_data["@odata.count"] = len(cash_accounts)
    return response_data # Removed jsonable_encoder

@mock_router.get("/Assets/WealthArc.Instrument", response_model=InstrumentODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_instruments(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/Assets/WealthArc.Instrument | Params: {req.query_params} (ignored)")
    instruments = [a for a in EXAMPLE_ASSETS if isinstance(a, Instrument)]
    response_data = {
        "@odata.context": get_odata_context(req, "Assets/WealthArc.Instrument"),
        "value": instruments
    }
    if cnt:
        response_data["@odata.count"] = len(instruments)
    return response_data # Removed jsonable_encoder

# Portfolios
@mock_router.get("/Portfolios", response_model=PortfolioODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_portfolios(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/Portfolios | Params: {req.query_params} (ignored)")
    response_data = {
        "@odata.context": get_odata_context(req, "Portfolios"),
        "value": EXAMPLE_PORTFOLIOS
    }
    if cnt:
        response_data["@odata.count"] = len(EXAMPLE_PORTFOLIOS)
    return response_data # Removed jsonable_encoder

@mock_router.get("/Portfolios/{key}", response_model=PortfolioODataResponse, response_model_exclude_unset=True)
async def get_mock_portfolio_by_key(key: int, req: Request):
    logger.info(f"GET /mock_api/v1/Portfolios/{key} | Params: {req.query_params} (ignored)")
    portfolio = next((p for p in EXAMPLE_PORTFOLIOS if p.id == key), None)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Mock Portfolio not found")
    response_data = {
        "@odata.context": get_odata_context(req, "Portfolios", is_entity=True),
        "value": portfolio
    }
    return response_data # Removed jsonable_encoder

# Positions
@mock_router.get("/Positions", response_model=PositionODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_positions(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/Positions | Params: {req.query_params} (ignored)")
    response_data = {
        "@odata.context": get_odata_context(req, "Positions"),
        "value": EXAMPLE_POSITIONS
    }
    if cnt:
        response_data["@odata.count"] = len(EXAMPLE_POSITIONS)
    return response_data # Removed jsonable_encoder

@mock_router.get("/Positions/{key}", response_model=PositionODataResponse, response_model_exclude_unset=True)
async def get_mock_position_by_key(key: int, req: Request):
    logger.info(f"GET /mock_api/v1/Positions/{key} | Params: {req.query_params} (ignored)")
    position = next((p for p in EXAMPLE_POSITIONS if p.id == key), None)
    if not position:
        raise HTTPException(status_code=404, detail="Mock Position not found")
    response_data = {
        "@odata.context": get_odata_context(req, "Positions", is_entity=True),
        "value": position
    }
    return response_data # Removed jsonable_encoder

# Transactions
@mock_router.get("/Transactions", response_model=TransactionODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_transactions(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/Transactions | Params: {req.query_params} (ignored)")
    response_data = {
        "@odata.context": get_odata_context(req, "Transactions"),
        "value": EXAMPLE_TRANSACTIONS
    }
    if cnt:
        response_data["@odata.count"] = len(EXAMPLE_TRANSACTIONS)
    return response_data # Removed jsonable_encoder

@mock_router.get("/Transactions/{key}", response_model=TransactionODataResponse, response_model_exclude_unset=True)
async def get_mock_transaction_by_key(key: int, req: Request):
    logger.info(f"GET /mock_api/v1/Transactions/{key} | Params: {req.query_params} (ignored)")
    transaction = next((t for t in EXAMPLE_TRANSACTIONS if t.id == key), None)
    if not transaction:
        raise HTTPException(status_code=404, detail="Mock Transaction not found")
    response_data = {
        "@odata.context": get_odata_context(req, "Transactions", is_entity=True),
        "value": transaction
    }
    return response_data # Removed jsonable_encoder

# PortfolioDailyMetrics
@mock_router.get("/PortfoliosDailyMetrics", response_model=PortfolioDailyMetricsODataCollectionResponse, response_model_exclude_unset=True)
async def get_mock_portfolio_daily_metrics_list(req: Request, cnt: Optional[bool]=Query(None, alias="$count")):
    logger.info(f"GET /mock_api/v1/PortfoliosDailyMetrics | Params: {req.query_params} (ignored)")
    response_data = {
        "@odata.context": get_odata_context(req, "PortfoliosDailyMetrics"),
        "value": EXAMPLE_PORTFOLIO_DAILY_METRICS
    }
    if cnt:
        response_data["@odata.count"] = len(EXAMPLE_PORTFOLIO_DAILY_METRICS)
    return response_data # Removed jsonable_encoder

@mock_router.get("/PortfoliosDailyMetrics/{key}", response_model=PortfolioDailyMetricsODataResponse, response_model_exclude_unset=True)
async def get_mock_portfolio_daily_metrics_by_key(key: int, req: Request):
    logger.info(f"GET /mock_api/v1/PortfoliosDailyMetrics/{key} | Params: {req.query_params} (ignored)")
    metrics = next((m for m in EXAMPLE_PORTFOLIO_DAILY_METRICS if m.id == key), None)
    if not metrics:
        raise HTTPException(status_code=404, detail="Mock PortfolioDailyMetrics not found")
    response_data = {
        "@odata.context": get_odata_context(req, "PortfoliosDailyMetrics", is_entity=True),
        "value": metrics
    }
    return response_data # Removed jsonable_encoder

# === Include Routers in Main App ===
app.include_router(bridge_router)
app.include_router(gateway_router)
app.include_router(mock_router)

# === Root Endpoint ===
@app.get("/", tags=["Root"])
async def root(): return {"message": "Combined API Service Running", "bridge_docs": "/docs#/Browser%20Bridge", "gateway_docs": "/docs#/OData%20Gateway", "mock_api_docs": "/docs#/Mock%20Vidar%20API", "live_view_example": "/live/{task_id}"}

# === Main Execution Block ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting combined server on port {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
