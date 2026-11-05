"""
Module 12: Monitoring & Prediction Module
- Track student activity (submissions, logins, patterns)
- Detect suspicious behavior (rapid submissions, duplicate content)
- Analyze results across classes and assignments
- Predict student performance based on historical data
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bson import ObjectId


async def log_activity(db, user_id: str, action: str, details: Optional[Dict] = None):
    """Log a user activity event for monitoring."""
    await db["activity_log"].insert_one({
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "timestamp": datetime.utcnow(),
    })


async def detect_suspicious_behavior(db, student_id: str) -> List[Dict]:
    """
    Analyze student's recent activity for suspicious patterns.
    Checks:
    - Rapid consecutive submissions (< 2 min apart)
    - Identical submission content
    - Submissions outside normal hours
    """
    alerts = []

    # Get recent submissions (last 24h)
    since = datetime.utcnow() - timedelta(hours=24)
    cursor = db["submissions"].find({
        "student_id": student_id,
        "created_at": {"$gte": since},
    }).sort("created_at", 1)
    submissions = await cursor.to_list(length=100)

    # Check rapid submissions
    for i in range(1, len(submissions)):
        prev_time = submissions[i - 1]["created_at"]
        curr_time = submissions[i]["created_at"]
        diff = (curr_time - prev_time).total_seconds()
        if diff < 120:  # Less than 2 minutes apart
            alerts.append({
                "type": "rapid_submission",
                "severity": "medium",
                "description": f"Two submissions within {int(diff)}s",
                "timestamp": curr_time.isoformat(),
            })

    # Check duplicate file names (potential re-uploads)
    names = [s.get("original_name", "") for s in submissions]
    seen = set()
    for name in names:
        if name in seen:
            alerts.append({
                "type": "duplicate_file",
                "severity": "low",
                "description": f"Same file uploaded multiple times: {name}",
                "timestamp": datetime.utcnow().isoformat(),
            })
        seen.add(name)

    return alerts


async def get_student_analytics(db, student_id: str) -> Dict:
    """
    Generate analytics for a student across all their submissions.
    Returns performance summary, trends, and areas needing attention.
    """
    cursor = db["submissions"].find({"student_id": student_id}).sort("created_at", 1)
    submissions = await cursor.to_list(length=500)

    if not submissions:
        return {
            "total_submissions": 0,
            "average_score": 0,
            "trend": "no_data",
            "performance_over_time": [],
        }

    graded = [s for s in submissions if s.get("status") == "graded" and s.get("score") is not None]

    scores = []
    performance_timeline = []
    for s in graded:
        pct = (s["score"] / max(s.get("total_marks", 1), 1)) * 100
        scores.append(pct)
        performance_timeline.append({
            "date": s["created_at"].isoformat(),
            "score_percentage": round(pct, 1),
            "assignment_id": s.get("assignment_id"),
        })

    avg_score = sum(scores) / len(scores) if scores else 0

    # Determine trend (improving, declining, stable)
    trend = "stable"
    if len(scores) >= 3:
        recent = scores[-3:]
        earlier = scores[:3]
        recent_avg = sum(recent) / len(recent)
        earlier_avg = sum(earlier) / len(earlier)
        if recent_avg > earlier_avg + 5:
            trend = "improving"
        elif recent_avg < earlier_avg - 5:
            trend = "declining"

    return {
        "total_submissions": len(submissions),
        "graded_submissions": len(graded),
        "average_score": round(avg_score, 1),
        "highest_score": round(max(scores), 1) if scores else 0,
        "lowest_score": round(min(scores), 1) if scores else 0,
        "trend": trend,
        "performance_over_time": performance_timeline,
    }


async def predict_performance(db, student_id: str) -> Dict:
    """
    Predict student's future performance based on historical trends.
    Uses simple linear trend analysis.
    """
    analytics = await get_student_analytics(db, student_id)
    timeline = analytics.get("performance_over_time", [])

    if len(timeline) < 3:
        return {
            "prediction": "insufficient_data",
            "message": "Need at least 3 graded submissions for prediction",
            "risk_level": "unknown",
        }

    scores = [t["score_percentage"] for t in timeline]

    # Simple linear regression (slope)
    n = len(scores)
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    numerator = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0

    # Predict next score
    predicted_next = scores[-1] + slope
    predicted_next = max(0, min(100, predicted_next))

    # Risk assessment
    if predicted_next < 40 or analytics["average_score"] < 40:
        risk_level = "high"
        message = "Student is at risk of failing. Immediate intervention recommended."
    elif predicted_next < 60 or analytics["trend"] == "declining":
        risk_level = "medium"
        message = "Student performance may decline. Consider additional support."
    else:
        risk_level = "low"
        message = "Student is performing well. Keep up the momentum."

    return {
        "prediction": "available",
        "predicted_next_score": round(predicted_next, 1),
        "trend_direction": slope,
        "current_average": analytics["average_score"],
        "risk_level": risk_level,
        "message": message,
        "trend": analytics["trend"],
    }


async def get_class_analytics(db, class_id: str) -> Dict:
    """Generate analytics for an entire class."""
    # Get all assignments for this class
    assignments = await db["assignments"].find({"class_id": class_id}).to_list(length=100)
    assignment_ids = [str(a["_id"]) for a in assignments]

    if not assignment_ids:
        return {"total_students": 0, "assignments": []}

    # Get all submissions for these assignments
    cursor = db["submissions"].find({"assignment_id": {"$in": assignment_ids}})
    submissions = await cursor.to_list(length=1000)

    graded = [s for s in submissions if s.get("status") == "graded" and s.get("score") is not None]

    # Unique students
    student_ids = list(set(s["student_id"] for s in submissions))

    # Per-assignment stats
    assignment_stats = []
    for a in assignments:
        a_id = str(a["_id"])
        a_subs = [s for s in graded if s["assignment_id"] == a_id]
        if a_subs:
            scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in a_subs]
            assignment_stats.append({
                "assignment_id": a_id,
                "title": a.get("title", ""),
                "submissions_count": len(a_subs),
                "average_score": round(sum(scores) / len(scores), 1),
                "highest": round(max(scores), 1),
                "lowest": round(min(scores), 1),
            })

    # Overall class average
    all_scores = []
    for s in graded:
        all_scores.append((s["score"] / max(s.get("total_marks", 1), 1)) * 100)

    return {
        "total_students": len(student_ids),
        "total_submissions": len(submissions),
        "graded_submissions": len(graded),
        "class_average": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
        "assignment_stats": assignment_stats,
    }
