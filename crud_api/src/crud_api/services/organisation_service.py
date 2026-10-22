# Directions, services, agents (aucune regle particuliere : CRUD + contraintes de la base)
from crud_api.models import Agent, Direction, Service
from crud_api.services.base import CRUDService


class DirectionService(CRUDService[Direction]):
    model = Direction
    label = "Direction"


class ServiceService(CRUDService[Service]):
    model = Service
    label = "Service"


class AgentService(CRUDService[Agent]):
    model = Agent
    label = "Agent"


direction_service = DirectionService()
service_service = ServiceService()
agent_service = AgentService()
