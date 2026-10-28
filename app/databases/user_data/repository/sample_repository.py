"""
Sample Repository - CRUD operations for Sample model
"""
from typing import Optional, List

from ..models import Sample, SampleView
from ..database import session_generator


def get_all_samples(
    page: int = 1,
    page_size: int = 20,
    is_active: Optional[bool] = None
) -> tuple[List[Sample], int]:
    """
    Get all samples with pagination and optional active filter

    Returns:
        Tuple of (samples list, total count)
    """
    with session_generator() as db:
        query = db.query(Sample)

        if is_active is not None:
            query = query.filter(Sample.is_active == is_active)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        samples = query.order_by(Sample.sort_order.asc(), Sample.id.asc()).offset(offset).limit(page_size).all()

        return samples, total


def get_active_samples() -> List[Sample]:
    """
    Get all active samples (for public frontend display)
    """
    with session_generator() as db:
        return db.query(Sample)\
            .filter(Sample.is_active == True)\
            .order_by(Sample.sort_order.asc(), Sample.id.asc())\
            .all()


def get_sample_by_id(sample_id: int) -> Optional[Sample]:
    """Get sample by ID"""
    with session_generator() as db:
        return db.query(Sample).filter(Sample.id == sample_id).first()


def create_sample(
    file_name: str,
    description: str,
    task_id: str,
    sort_order: int = 0,
    is_active: bool = True
) -> Sample:
    """Create a new sample"""
    with session_generator() as db:
        sample = Sample(
            file_name=file_name,
            description=description,
            task_id=task_id,
            sort_order=sort_order,
            is_active=is_active
        )
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample


def update_sample(
    sample_id: int,
    file_name: Optional[str] = None,
    description: Optional[str] = None,
    task_id: Optional[str] = None,
    sort_order: Optional[int] = None,
    is_active: Optional[bool] = None
) -> Optional[Sample]:
    """Update an existing sample"""
    with session_generator() as db:
        sample = db.query(Sample).filter(Sample.id == sample_id).first()
        if sample:
            if file_name is not None:
                sample.file_name = file_name
            if description is not None:
                sample.description = description
            if task_id is not None:
                sample.task_id = task_id
            if sort_order is not None:
                sample.sort_order = sort_order
            if is_active is not None:
                sample.is_active = is_active
            db.commit()
            db.refresh(sample)
        return sample


def delete_sample(sample_id: int) -> bool:
    """Delete a sample by ID"""
    with session_generator() as db:
        sample = db.query(Sample).filter(Sample.id == sample_id).first()
        if sample:
            db.delete(sample)
            db.commit()
            return True
        return False


def get_sample_count(is_active: Optional[bool] = None) -> int:
    """Get total sample count"""
    with session_generator() as db:
        query = db.query(Sample)
        if is_active is not None:
            query = query.filter(Sample.is_active == is_active)
        return query.count()


def get_sample_by_task_id(task_id: str) -> Optional[Sample]:
    """Get sample by task_id"""
    with session_generator() as db:
        return db.query(Sample).filter(Sample.task_id == task_id).first()


# =============================================================================
# Sample View (访问记录) functions
# =============================================================================

def record_sample_view(sample_id: int, ip_address: str, user_agent: str = None) -> SampleView:
    """Record a sample view"""
    with session_generator() as db:
        view = SampleView(
            sample_id=sample_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(view)
        db.commit()
        db.refresh(view)
        return view


def get_sample_views(
    sample_id: int,
    page: int = 1,
    page_size: int = 50
) -> tuple[List[SampleView], int]:
    """Get sample views with pagination"""
    with session_generator() as db:
        query = db.query(SampleView).filter(SampleView.sample_id == sample_id)

        total = query.count()

        offset = (page - 1) * page_size
        views = query.order_by(SampleView.viewed_at.desc()).offset(offset).limit(page_size).all()

        return views, total


def get_sample_view_count(sample_id: int) -> int:
    """Get total view count for a sample"""
    with session_generator() as db:
        return db.query(SampleView).filter(SampleView.sample_id == sample_id).count()


def get_all_samples_with_view_count(
    page: int = 1,
    page_size: int = 20,
    is_active: Optional[bool] = None
) -> tuple[List[dict], int]:
    """
    Get all samples with their view counts
    """
    with session_generator() as db:
        from sqlalchemy import func as sql_func

        query = db.query(Sample)

        if is_active is not None:
            query = query.filter(Sample.is_active == is_active)

        total = query.count()

        offset = (page - 1) * page_size
        samples = query.order_by(Sample.sort_order.asc(), Sample.id.asc()).offset(offset).limit(page_size).all()

        # Get view counts for each sample
        result = []
        for sample in samples:
            view_count = db.query(SampleView).filter(SampleView.sample_id == sample.id).count()
            sample_dict = sample.to_dict()
            sample_dict['view_count'] = view_count
            result.append(sample_dict)

        return result, total
