from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)

    answer: Mapped[str] = mapped_column(Text, nullable=False)

    result_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    result_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    chart_config: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    generated_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_retried: Mapped[bool] = mapped_column(default=False, nullable=False)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="analyses")
    user: Mapped["User"] = relationship(back_populates="analyses")