from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from db.models import Subject, Topic, Subtopic, Question, Option, Admin, Attempt
from sqlalchemy import select, func, desc, case
from sqlalchemy.orm import selectinload
from db.models import User
from datetime import datetime, timedelta


class Repo:
    def __init__(self, session: AsyncSession):
        self.s = session
    async def subject_exists(self, code: str) -> bool:
        res = await self.s.execute(select(Subject.id).where(Subject.code == code))
        return res.scalar_one_or_none() is not None

    async def create_subject(self, code: str, name: str) -> int:
        code = code.strip().lower()
        name = name.strip()
        s = Subject(code=code, name=name)
        self.s.add(s)
        await self.s.commit()
        return s.id

    async def create_topic(self, subject_id: int, name: str) -> int:
        t = Topic(subject_id=subject_id, name=name.strip())
        self.s.add(t)
        await self.s.commit()
        return t.id

    async def get_subject_by_code(self, code: str) -> Subject | None:
        res = await self.s.execute(select(Subject).where(Subject.code == code.strip().lower()))
        return res.scalar_one_or_none()

    async def list_subjects(self) -> list[Subject]:
        res = await self.s.execute(select(Subject).order_by(Subject.id.asc()))
        return list(res.scalars().all())

    async def list_user_tg_ids(self) -> list[int]:
        res = await self.s.execute(select(User.tg_id).order_by(User.id.asc()))
        return [int(x) for x in res.scalars().all()]

    async def is_admin(self, tg_id: int) -> bool:
        res = await self.s.execute(select(Admin.id).where(Admin.tg_id == tg_id))
        return res.scalar_one_or_none() is not None

    async def list_admins(self) -> list[int]:
        res = await self.s.execute(select(Admin.tg_id).order_by(Admin.created_at.asc()))
        return list(res.scalars().all())

    async def add_admin(self, tg_id: int, added_by_tg_id: int | None = None) -> bool:
        # returns True if added, False if already existed
        if await self.is_admin(tg_id):
            return False
        self.s.add(Admin(tg_id=tg_id, added_by_tg_id=added_by_tg_id))
        await self.s.commit()
        return True

    async def remove_admin(self, tg_id: int) -> bool:
        # returns True if removed, False if not found
        res = await self.s.execute(select(Admin.id).where(Admin.tg_id == tg_id))
        admin_id = res.scalar_one_or_none()
        if admin_id is None:
            return False
        await self.s.execute(delete(Admin).where(Admin.id == admin_id))
        await self.s.commit()
        return True

    async def get_subjects(self) -> list[Subject]:
        res = await self.s.execute(select(Subject).order_by(Subject.id.asc()))
        return list(res.scalars().all())

    async def get_topics(self, subject_id: int) -> list[Topic]:
        res = await self.s.execute(
            select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.id.asc())
        )
        return list(res.scalars().all())

    async def get_subtopics(self, topic_id: int) -> list[Subtopic]:
        res = await self.s.execute(
            select(Subtopic).where(Subtopic.topic_id == topic_id).order_by(Subtopic.id.asc())
        )
        return list(res.scalars().all())

    async def create_subtopic(self, topic_id: int, name: str) -> int:
        st = Subtopic(topic_id=topic_id, name=name.strip())
        self.s.add(st)
        await self.s.commit()
        return st.id

    async def create_question(
        self,
        subject_id: int,
        topic_id: int,
        subtopic_id: int | None,
        text: str,
        qtype: str,  # "single" | "multi"
        explanation: str,
        image_file_id: str | None,
        options: list[tuple[str, bool]],  # (text, is_correct)
    ) -> int:
        q = Question(
            subject_id=subject_id,
            topic_id=topic_id,
            subtopic_id=subtopic_id,
            text=text,
            qtype=qtype,
            explanation=explanation,
            image_file_id=image_file_id,
        )
        self.s.add(q)
        await self.s.flush()  # получим q.id

        for opt_text, is_correct in options:
            self.s.add(Option(question_id=q.id, text=opt_text, is_correct=is_correct))

        await self.s.commit()
        return q.id
    async def count_questions(self, subject_id: int | None = None, topic_id: int | None = None) -> int:
        q = select(func.count(Question.id))
        if subject_id is not None:
            q = q.where(Question.subject_id == subject_id)
        if topic_id is not None:
            q = q.where(Question.topic_id == topic_id)
        res = await self.s.execute(q)
        return int(res.scalar_one())

    async def list_questions_page(
        self,
        offset: int,
        limit: int,
        subject_id: int | None = None,
        topic_id: int | None = None,
    ) -> list[Question]:
        q = (
            select(Question)
            .order_by(Question.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if subject_id is not None:
            q = q.where(Question.subject_id == subject_id)
        if topic_id is not None:
            q = q.where(Question.topic_id == topic_id)
        res = await self.s.execute(q)
        return list(res.scalars().all())

    async def get_question_full(self, qid: int) -> Question | None:
        q = (
            select(Question)
            .where(Question.id == qid)
        )
        res = await self.s.execute(q)
        return res.scalar_one_or_none()

    async def get_options(self, qid: int) -> list[Option]:
        res = await self.s.execute(select(Option).where(Option.question_id == qid).order_by(Option.id.asc()))
        return list(res.scalars().all())

    async def delete_question(self, qid: int) -> bool:
        q = await self.s.execute(select(Question).where(Question.id == qid))
        obj = q.scalar_one_or_none()
        if not obj:
            return False
        await self.s.delete(obj)
        await self.s.commit()
        return True

    async def get_correct_option_ids(self, qid: int) -> set[int]:
        res = await self.s.execute(
            select(Option.id).where(Option.question_id == qid, Option.is_correct == True)
        )
        return set(res.scalars().all())

    async def get_options(self, qid: int) -> list[Option]:
        res = await self.s.execute(
            select(Option).where(Option.question_id == qid).order_by(Option.id.asc())
        )
        return list(res.scalars().all())

    async def pick_next_question_id(
            self,
            user_id: int,
            subject_id: int,
            topic_id: int,
            subtopic_ids: list[int] | None,
            recent_limit: int = 200,
    ) -> int | None:
        # 1) исключаем недавно решённые
        recent = await self.s.execute(
            select(Attempt.question_id)
            .where(Attempt.user_id == user_id)
            .order_by(desc(Attempt.created_at))
            .limit(recent_limit)
        )
        recent_ids = set(recent.scalars().all())

        q = select(Question.id).where(
            Question.subject_id == subject_id,
            Question.topic_id == topic_id,
        )

        if subtopic_ids:
            q = q.where(Question.subtopic_id.in_(subtopic_ids))

        if recent_ids:
            q = q.where(~Question.id.in_(recent_ids))

        q = q.order_by(func.random()).limit(1)
        res = await self.s.execute(q)
        return res.scalar_one_or_none()

    async def get_question(self, qid: int) -> Question | None:
        res = await self.s.execute(select(Question).where(Question.id == qid))
        return res.scalar_one_or_none()

    async def add_attempt(
            self,
            user_id: int,
            question_id: int,
            is_correct: bool,
            chosen_option_ids: list[int],
    ) -> None:
        att = Attempt(
            user_id=user_id,
            question_id=question_id,
            is_correct=is_correct,
            chosen_option_ids=",".join(map(str, chosen_option_ids)),
        )
        self.s.add(att)
        await self.s.commit()

    async def get_topic_name(self, topic_id: int) -> str:
        res = await self.s.execute(select(Topic.name).where(Topic.id == topic_id))
        return res.scalar_one()

    async def get_user_by_tg_id(self, tg_id: int) -> User | None:
        res = await self.s.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        uname = username.strip().lstrip("@").lower()
        if not uname:
            return None
        res = await self.s.execute(select(User).where(func.lower(User.username) == uname))
        return res.scalar_one_or_none()

    async def get_or_create_user(
        self,
        tg_id: int,
        full_name: str = "-",
        grade_group: str = "8-",
        username: str | None = None,
    ) -> User:
        res = await self.s.execute(select(User).where(User.tg_id == tg_id))
        u = res.scalar_one_or_none()
        norm_username = (username or "").strip().lstrip("@").lower() or None
        if u:
            changed = False
            if full_name and u.full_name != full_name:
                u.full_name = full_name
                changed = True
            if norm_username and u.username != norm_username:
                u.username = norm_username
                changed = True
            if changed:
                await self.s.commit()
            return u
        u = User(tg_id=tg_id, full_name=full_name, grade_group=grade_group, username=norm_username)
        self.s.add(u)
        await self.s.commit()
        return u

    async def user_totals(self, user_id: int) -> tuple[int, int]:
        total = await self.s.execute(select(func.count(Attempt.id)).where(Attempt.user_id == user_id))
        correct = await self.s.execute(
            select(func.count(Attempt.id)).where(Attempt.user_id == user_id, Attempt.is_correct == True))
        return int(total.scalar_one()), int(correct.scalar_one())

    async def solved_by_topic(self, user_id: int, limit: int = 20) -> list[tuple[str, int]]:
        # topic_name, solved_count
        q = (
            select(Topic.name, func.count(Attempt.id))
            .join(Question, Question.topic_id == Topic.id)
            .join(Attempt, Attempt.question_id == Question.id)
            .where(Attempt.user_id == user_id)
            .group_by(Topic.name)
            .order_by(func.count(Attempt.id).desc())
            .limit(limit)
        )
        res = await self.s.execute(q)
        return [(name, int(cnt)) for name, cnt in res.all()]

    async def accuracy_by_day(self, user_id: int, days: int = 14) -> list[tuple[str, int, int]]:
        # returns [(YYYY-MM-DD, solved, correct), ...] in ascending date order
        date_col = func.date(Attempt.created_at)
        cutoff = datetime.utcnow() - timedelta(days=days - 1)
        q = (
            select(
                date_col.label("d"),
                func.count(Attempt.id).label("solved"),
                func.sum(case((Attempt.is_correct == True, 1), else_=0)).label("correct"),
            )
            .where(Attempt.user_id == user_id, Attempt.created_at >= cutoff)
            .group_by(date_col)
            .order_by(date_col.asc())
        )
        res = await self.s.execute(q)
        return [(str(d), int(solved), int(correct or 0)) for d, solved, correct in res.all()]

    async def recent_attempts(self, user_id: int, limit: int = 12) -> list[tuple[datetime, str, bool]]:
        q = (
            select(Attempt.created_at, Topic.name, Attempt.is_correct)
            .join(Question, Question.id == Attempt.question_id)
            .join(Topic, Topic.id == Question.topic_id)
            .where(Attempt.user_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
        res = await self.s.execute(q)
        return [(dt, topic, ok) for dt, topic, ok in res.all()]
