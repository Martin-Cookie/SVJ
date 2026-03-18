"""Tests for voting vote aggregation logic."""
from sqlalchemy import func, case

from app.models import (
    Voting, VotingItem, Ballot, BallotVote, Owner, Unit, OwnerUnit,
    VotingStatus, BallotStatus, VoteValue,
)
from app.utils import strip_diacritics


def _create_owner(db, first_name, last_name, idx=1):
    """Helper to create an Owner."""
    from app.utils import strip_diacritics
    name_wt = f"{last_name} {first_name}"
    owner = Owner(
        first_name=first_name,
        last_name=last_name,
        name_with_titles=name_wt,
        name_normalized=strip_diacritics(name_wt),
    )
    db.add(owner)
    db.flush()
    return owner


def _create_voting_with_items(db, item_count=2):
    """Helper to create Voting with VotingItems."""
    voting = Voting(title="Test hlasování", status=VotingStatus.ACTIVE)
    db.add(voting)
    db.flush()

    items = []
    for i in range(item_count):
        item = VotingItem(voting_id=voting.id, order=i + 1, title=f"Bod {i + 1}")
        db.add(item)
        db.flush()
        items.append(item)

    return voting, items


def test_vote_aggregation_basic(db_session):
    """3 ballots with various votes should produce correct aggregated counts."""
    voting, items = _create_voting_with_items(db_session, item_count=1)
    item = items[0]

    owners = [_create_owner(db_session, f"Jméno{i}", f"Příjmení{i}") for i in range(3)]

    # Create 3 processed ballots with different votes
    votes_data = [
        (owners[0], VoteValue.FOR, 100),
        (owners[1], VoteValue.AGAINST, 50),
        (owners[2], VoteValue.FOR, 75),
    ]
    for owner, vote_val, total_v in votes_data:
        ballot = Ballot(
            voting_id=voting.id,
            owner_id=owner.id,
            status=BallotStatus.PROCESSED,
            total_votes=total_v,
        )
        db_session.add(ballot)
        db_session.flush()

        bv = BallotVote(
            ballot_id=ballot.id,
            voting_item_id=item.id,
            vote=vote_val,
            votes_count=total_v,
        )
        db_session.add(bv)

    db_session.flush()

    # Aggregate using the same SQL pattern as the router
    result = (
        db_session.query(
            func.sum(case((BallotVote.vote == VoteValue.FOR, BallotVote.votes_count), else_=0)).label("votes_for"),
            func.sum(case((BallotVote.vote == VoteValue.AGAINST, BallotVote.votes_count), else_=0)).label("votes_against"),
            func.sum(func.coalesce(BallotVote.votes_count, 0)).label("votes_total"),
        )
        .join(Ballot, BallotVote.ballot_id == Ballot.id)
        .filter(
            Ballot.voting_id == voting.id,
            Ballot.status == BallotStatus.PROCESSED,
            BallotVote.voting_item_id == item.id,
        )
        .one()
    )

    assert result.votes_for == 175  # 100 + 75
    assert result.votes_against == 50
    assert result.votes_total == 225  # 100 + 50 + 75


def test_vote_aggregation_empty(db_session):
    """No processed ballots should return zeros."""
    voting, items = _create_voting_with_items(db_session, item_count=1)

    result = (
        db_session.query(
            func.coalesce(func.sum(case((BallotVote.vote == VoteValue.FOR, BallotVote.votes_count), else_=0)), 0).label("votes_for"),
            func.coalesce(func.sum(case((BallotVote.vote == VoteValue.AGAINST, BallotVote.votes_count), else_=0)), 0).label("votes_against"),
        )
        .join(Ballot, BallotVote.ballot_id == Ballot.id)
        .filter(
            Ballot.voting_id == voting.id,
            Ballot.status == BallotStatus.PROCESSED,
            BallotVote.voting_item_id == items[0].id,
        )
        .one()
    )

    assert result.votes_for == 0
    assert result.votes_against == 0


def test_vote_aggregation_null_votes(db_session):
    """NULL votes_count should coalesce to 0."""
    voting, items = _create_voting_with_items(db_session, item_count=1)
    owner = _create_owner(db_session, "Test", "User")

    ballot = Ballot(
        voting_id=voting.id,
        owner_id=owner.id,
        status=BallotStatus.PROCESSED,
        total_votes=100,
    )
    db_session.add(ballot)
    db_session.flush()

    # BallotVote with votes_count=None
    bv = BallotVote(
        ballot_id=ballot.id,
        voting_item_id=items[0].id,
        vote=VoteValue.FOR,
        votes_count=None,
    )
    db_session.add(bv)
    db_session.flush()

    result = (
        db_session.query(
            func.sum(func.coalesce(BallotVote.votes_count, 0)).label("votes_total"),
        )
        .join(Ballot, BallotVote.ballot_id == Ballot.id)
        .filter(
            Ballot.voting_id == voting.id,
            Ballot.status == BallotStatus.PROCESSED,
        )
        .one()
    )

    assert result.votes_total == 0
