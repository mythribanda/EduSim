"""add classes and teacher subject models

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-07 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    # Step 1: Handle legacy curriculum classes table if present
    if "classes" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("classes")]
        # If 'classes' is the old curriculum table (has 'display_order' and not 'grade_level')
        if "display_order" in columns and "grade_level" not in columns:
            if "curriculum_classes" not in existing_tables:
                op.rename_table("classes", "curriculum_classes")
            else:
                op.drop_table("classes")

    # Step 2: Create new classes table
    if "classes" not in existing_tables:
        op.create_table(
            'classes',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('grade_level', sa.String(length=50), nullable=False),
            sa.Column('institution_id', sa.UUID(), nullable=True),
            sa.Column('created_by', sa.UUID(), nullable=False),
            sa.Column('join_code', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_classes_created_by'), 'classes', ['created_by'], unique=False)
        op.create_index(op.f('ix_classes_institution_id'), 'classes', ['institution_id'], unique=False)
        op.create_index(op.f('ix_classes_join_code'), 'classes', ['join_code'], unique=True)

    # Step 3: Create teacher_class_subjects table
    if "teacher_class_subjects" not in existing_tables:
        op.create_table(
            'teacher_class_subjects',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('teacher_id', sa.UUID(), nullable=False),
            sa.Column('class_id', sa.UUID(), nullable=False),
            sa.Column('subject', sa.String(length=100), nullable=False),
            sa.Column('is_primary', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('teacher_id', 'class_id', 'subject', name='uq_teacher_class_subject')
        )
        op.create_index(op.f('ix_teacher_class_subjects_class_id'), 'teacher_class_subjects', ['class_id'], unique=False)
        op.create_index(op.f('ix_teacher_class_subjects_subject'), 'teacher_class_subjects', ['subject'], unique=False)
        op.create_index(op.f('ix_teacher_class_subjects_teacher_id'), 'teacher_class_subjects', ['teacher_id'], unique=False)
        op.create_index('ix_tcs_class_subject', 'teacher_class_subjects', ['class_id', 'subject'], unique=False)
        op.create_index('ix_tcs_teacher_subject', 'teacher_class_subjects', ['teacher_id', 'subject'], unique=False)

    # Step 4: Create student_enrollments table
    if "student_enrollments" not in existing_tables:
        op.create_table(
            'student_enrollments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('student_id', sa.UUID(), nullable=False),
            sa.Column('class_id', sa.UUID(), nullable=False),
            sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
            sa.CheckConstraint("status IN ('active', 'inactive')", name='chk_enrollment_status'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'class_id', name='uq_student_class_enrollment')
        )
        op.create_index(op.f('ix_student_enrollments_class_id'), 'student_enrollments', ['class_id'], unique=False)
        op.create_index(op.f('ix_student_enrollments_student_id'), 'student_enrollments', ['student_id'], unique=False)
        op.create_index('ix_enrollment_class_status', 'student_enrollments', ['class_id', 'status'], unique=False)
        op.create_index('ix_enrollment_student_status', 'student_enrollments', ['student_id', 'status'], unique=False)



def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if "student_enrollments" in existing_tables:
        op.drop_table('student_enrollments')
    if "teacher_class_subjects" in existing_tables:
        op.drop_table('teacher_class_subjects')
    if "classes" in existing_tables:
        op.drop_table('classes')

    if "curriculum_classes" in existing_tables:
        op.rename_table("curriculum_classes", "classes")
