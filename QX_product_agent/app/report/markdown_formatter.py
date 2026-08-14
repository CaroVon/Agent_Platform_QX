def build_report(title: str, sections: list):

    report = f"# {title}\n\n"

    for section in sections:
        report += section + "\n\n"

    return report
