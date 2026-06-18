def check_eligibility(student_profile: dict, scholarship: dict) -> dict:
    """Compare a student profile against a scholarship's requirements."""
    met, failed = [], []

    min_cgpa = scholarship.get('min_cgpa')
    if min_cgpa:
        student_cgpa = student_profile.get('cgpa', 0)
        if student_cgpa < float(min_cgpa):
            failed.append(f"CGPA too low: student has {student_cgpa}, requires {min_cgpa}")
        else:
            met.append(f"CGPA ok ({student_cgpa} >= {min_cgpa})")

    req_nationality = (scholarship.get('nationality') or '').lower()
    if req_nationality and req_nationality != 'any':
        student_nationality = student_profile.get('nationality', '').lower()
        if student_nationality not in req_nationality:
            failed.append(f"Nationality mismatch: student is {student_profile.get('nationality')}, requires {req_nationality}")
        else:
            met.append("Nationality ok")

    req_degree = (scholarship.get('degree_level') or '').lower()
    if req_degree and req_degree != 'any':
        student_degree = student_profile.get('degree_level', '').lower()
        if student_degree not in req_degree:
            failed.append(f"Degree level mismatch: student is {student_profile.get('degree_level')}, requires {req_degree}")
        else:
            met.append("Degree level ok")

    return {
        "scholarship": scholarship.get('name'),
        "student": student_profile.get('name'),
        "eligible": len(failed) == 0,
        "requirements_met": met,
        "requirements_failed": failed,
        "recommendation": "Eligible — recommend applying" if not failed else f"Not eligible: {'; '.join(failed)}",
    }
