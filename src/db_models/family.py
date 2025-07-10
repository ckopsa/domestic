import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Family(Base):
    __tablename__ = "families"
    id = Column(String, primary_key=True, index=True, default=lambda: "fam_" + str(uuid.uuid4())[:8])
    name = Column(String, nullable=False)
    admin_user_id = Column(String, nullable=False)  # References Keycloak user_id

    members = relationship("FamilyMember", back_populates="family")
    # Add a backref for workflow_instances if direct access from Family to its instances is desired
    # workflow_instances = relationship("WorkflowInstance", back_populates="family")

class FamilyMember(Base):
    __tablename__ = "family_members"
    id = Column(String, primary_key=True, index=True, default=lambda: "mem_" + str(uuid.uuid4())[:8])
    family_id = Column(String, ForeignKey("families.id"), nullable=False)
    user_id = Column(String, nullable=False)  # References Keycloak user_id
    role = Column(String, default="member")  # e.g., "admin", "member", "child"

    family = relationship("Family", back_populates="members")
