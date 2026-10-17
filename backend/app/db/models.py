"""SQLite tables for a project (one screenshot) and its code versions."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target: Mapped[str] = mapped_column(String(32), default="html_tailwind")
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(32), nullable=False)
    image_name: Mapped[str] = mapped_column(String(64), nullable=False)
    hint: Mapped[str] = mapped_column(Text, default="")

    versions: Mapped[list["Version"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Version.number",
    )


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship(back_populates="versions")
