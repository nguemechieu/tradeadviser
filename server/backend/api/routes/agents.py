"""
Agents & AI Pillar API Routes
Endpoints for AI agent deployment, configuration, and performance monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.backend.dependencies import get_db, get_current_user
from server.backend.models import Agent, AgentStatus, AgentAudit, User
from server.backend.schemas import UserSchema

router = APIRouter(prefix="/admin/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    model_type: str  # "ml", "rules", "hybrid", "llm"
    model_version: str
    config: dict | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    is_active: bool | None = None


@router.get("/overview")
async def get_agents_overview(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get platform-wide agent statistics."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    total_agents = db.query(Agent).count()
    active_agents = db.query(Agent).filter(Agent.is_active == True).count()
    
    # Top performing agents
    top_agents = db.query(Agent).order_by(Agent.cumulative_pnl.desc()).limit(5).all()
    
    return {
        "total": total_agents,
        "active": active_agents,
        "paused": total_agents - active_agents,
        "top_performers": [
            {
                "id": str(a.id),
                "name": a.name,
                "pnl": a.cumulative_pnl,
                "return": a.total_return,
                "trades": a.total_trades,
                "win_rate": a.win_rate
            }
            for a in top_agents
        ]
    }


@router.get("/")
async def list_agents(
    user_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """List all agents or filter by user and status."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(Agent)
    
    if user_id:
        query = query.filter(Agent.user_id == user_id)
    if status:
        query = query.filter(Agent.status == status)
    
    agents = query.all()
    
    return {
        "agents": [
            {
                "id": str(a.id),
                "user_id": str(a.user_id),
                "name": a.name,
                "model_type": a.model_type,
                "status": a.status.value,
                "is_active": a.is_active,
                "performance": {
                    "trades": a.total_trades,
                    "win_rate": a.win_rate,
                    "pnl": a.cumulative_pnl,
                    "return": a.total_return,
                    "sharpe": a.sharpe_ratio,
                    "max_drawdown": a.max_drawdown,
                },
                "last_trade": a.last_trade_time,
                "created_at": a.created_at,
            }
            for a in agents
        ]
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get detailed agent information."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    audit_logs = db.query(AgentAudit).filter(AgentAudit.agent_id == agent_id).order_by(
        AgentAudit.created_at.desc()
    ).limit(20).all()
    
    return {
        "id": str(agent.id),
        "user_id": str(agent.user_id),
        "name": agent.name,
        "description": agent.description,
        "model": {
            "type": agent.model_type,
            "version": agent.model_version,
            "config": agent.config,
        },
        "status": agent.status.value,
        "is_active": agent.is_active,
        "performance": {
            "total_trades": agent.total_trades,
            "win_rate": agent.win_rate,
            "cumulative_pnl": agent.cumulative_pnl,
            "total_return": agent.total_return,
            "sharpe_ratio": agent.sharpe_ratio,
            "max_drawdown": agent.max_drawdown,
        },
        "limits": {
            "max_position_size": agent.max_position_size,
            "daily_loss_limit": agent.daily_loss_limit,
        },
        "audit_log": [
            {
                "action": log.action,
                "details": log.details,
                "timestamp": log.created_at,
                "by": log.triggered_by,
            }
            for log in audit_logs
        ]
    }


@router.post("/")
async def create_agent(
    agent_data: AgentCreate,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Create a new agent deployment."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If no user_id specified, create for current user (if trader)
    if not user_id:
        if current_user.role == "trader":
            user_id = current_user.id
        else:
            raise HTTPException(status_code=400, detail="user_id required")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    agent = Agent(
        user_id=user.id,
        name=agent_data.name,
        description=agent_data.description,
        model_type=agent_data.model_type,
        model_version=agent_data.model_version,
        config=agent_data.config or {},
    )
    
    audit = AgentAudit(
        agent_id=agent.id,
        action="created",
        triggered_by=current_user.email
    )
    
    db.add(agent)
    db.add(audit)
    db.commit()
    
    return {
        "id": str(agent.id),
        "name": agent.name,
        "status": agent.status.value,
        "message": "Agent created successfully"
    }


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    update: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update agent configuration."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if update.name is not None:
        agent.name = update.name
    if update.description is not None:
        agent.description = update.description
    if update.config is not None:
        agent.config = update.config
    if update.is_active is not None:
        agent.is_active = update.is_active
    
    db.commit()
    
    return {"message": "Agent updated", "agent_id": agent_id}


@router.post("/{agent_id}/deploy")
async def deploy_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Deploy an agent to run."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = AgentStatus.DEPLOYING
    
    audit = AgentAudit(
        agent_id=agent.id,
        action="deploy",
        triggered_by=current_user.email
    )
    
    db.add(audit)
    db.commit()
    
    return {"message": "Agent deployment started", "status": "deploying"}


@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Stop a running agent."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = AgentStatus.STOPPED
    agent.is_active = False
    
    audit = AgentAudit(
        agent_id=agent.id,
        action="stopped",
        triggered_by=current_user.email
    )
    
    db.add(audit)
    db.commit()
    
    return {"message": "Agent stopped"}


@router.get("/{agent_id}/performance")
async def get_agent_performance(
    agent_id: str,
    period: str = "all",
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get agent performance metrics."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "agent_id": agent_id,
        "period": period,
        "metrics": {
            "total_trades": agent.total_trades,
            "win_rate": agent.win_rate,
            "cumulative_pnl": agent.cumulative_pnl,
            "total_return": f"{agent.total_return}%",
            "sharpe_ratio": agent.sharpe_ratio,
            "max_drawdown": f"{agent.max_drawdown}%" if agent.max_drawdown else None,
        }
    }
