"""Modèles SQLAlchemy du Backoffice"""

from __future__ import annotations

import enum
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
    Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class TimestampMixin:
    """Colonnes de date communes à toutes nos tables"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Branch(TimestampMixin, Base):
    """Une succursale physique de l'entreprise"""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    users: Mapped[list["User"]] = relationship(back_populates="branch")
    stock_items: Mapped[list["Stock"]] = relationship(back_populates="branch")

    def __repr__(self) -> str:
        return f"<Branch {self.id} {self.name!r}>"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    COMMON = "common"


class User(TimestampMixin, Base, UserMixin):
    """Un employé de l'entreprise"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.COMMON,
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(  # type: ignore[assignment]
        Boolean, nullable=False, default=True, server_default="true"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    branch: Mapped["Branch | None"] = relationship(back_populates="users")

    __table_args__ = (
        CheckConstraint(
            "(role = 'COMMON' AND branch_id IS NOT NULL) "
            "OR (role = 'ADMIN' AND branch_id IS NULL)",
            name="ck_users_role_branch_consistency"
        ),
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username!r} {self.role.value}>"


class Stock(TimestampMixin, Base):
    """Quantité d'un produit externe dans une succursale"""

    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    branch: Mapped["Branch"] = relationship(back_populates="stock_items")

    __table_args__ = (
        UniqueConstraint(
            "branch_id", "product_id", name="uq_stock_branch_product"
        ),
        CheckConstraint(
            "quantity >= 0", name="ck_stock_quantity_non_negative"
        ),
        Index("ix_stock_product_id", "product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Stock branch={self.branch_id} "
            f"product={self.product_id} qty={self.quantity}>"
        )
