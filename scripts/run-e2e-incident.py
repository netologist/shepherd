"""Executable script running end-to-end incident investigation against real Kind cluster."""

import asyncio
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir / "src"))

from shepherd.graph.router import SREEntryRouter
from shepherd.domain.schemas import InvestigationType, FeedbackReview
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()


async def main():
    console.print(
        Panel.fit(
            "[bold cyan]SRE AI Multi-Agent Incident Investigation[/bold cyan]\n"
            "[dim]Autonomous RCA Pipeline with Parallel Specialists & Live Kubernetes Querying[/dim]",
            border_style="cyan",
        )
    )

    router = SREEntryRouter()

    incident_prompt = (
        "INC-8088: Alert triggered for service 'order-api' in namespace 'ecommerce-demo'. "
        "Pod restarts and 504 Gateway Timeouts reported. Please find the root cause."
    )

    console.print(f"\n[bold yellow]1. Ingesting Incident:[/bold yellow] [white]{incident_prompt}[/white]\n")

    with console.status("[bold green]Running Multi-Agent Investigation Pipeline...[/bold green]"):
        result = await router.start_investigation(
            raw_input=incident_prompt,
            investigation_type=InvestigationType.INCIDENT_REVIEW,
            investigation_id="inv-kind-demo-8088",
        )

    final_report = result.get("final_report")
    if not final_report:
        console.print("[bold red]Investigation failed to produce a final report.[/bold red]")
        return

    # ── Display Summary ───────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold red]Primary Root Cause:[/bold red] {final_report.get('primary_root_cause')}\n\n"
            f"[bold]Category:[/bold] {final_report.get('category')} | "
            f"[bold]Confidence:[/bold] {final_report.get('confidence')} | "
            f"[bold]Cross-Validated:[/bold] {final_report.get('cross_validated')} | "
            f"[bold]Deep Dives:[/bold] {final_report.get('deep_dive_count')}",
            title=f"Incident Report: {final_report.get('incident_id')}",
            border_style="red" if final_report.get("confidence") == "high" else "yellow",
        )
    )

    # ── Evidence Chain ────────────────────────────────────────────────
    ev_table = Table(title="Specialist Evidence Chain", show_header=True, header_style="bold magenta")
    ev_table.add_column("Step / Source", style="dim", width=25)
    ev_table.add_column("Telemetry Observation", style="white")

    for idx, ev in enumerate(final_report.get("evidence_chain", []), start=1):
        ev_table.add_row(f"Evidence #{idx}", ev)
    console.print(ev_table)

    # ── Recommendations ───────────────────────────────────────────────
    rec_md = "### Immediate Recommendations:\n"
    for r in final_report.get("immediate_recommendations", []):
        rec_md += f"- **[Action]** {r}\n"
    rec_md += "\n### Short-Term Preventative Actions:\n"
    for r in final_report.get("short_term_recommendations", []):
        rec_md += f"- **[Fix]** {r}\n"
    console.print(Markdown(rec_md))

    # ── Post-Investigation Interactive Chat Turn ──────────────────────
    console.print("\n[bold cyan]2. Interactive Post-Investigation Chat Simulation:[/bold cyan]")
    chat_query = "What is the memory limit of the order-api pod, and what exit code caused the crash?"
    console.print(f"[bold green]SRE Query:[/bold green] {chat_query}")

    with console.status("[bold green]Chat Agent querying live cluster state & report context...[/bold green]"):
        chat_reply = await router.send_chat_message(
            investigation_id="inv-kind-demo-8088",
            message=chat_query,
        )

    console.print(Panel(chat_reply, title="Agent Response", border_style="green"))

    # ── Submit Feedback ───────────────────────────────────────────────
    feedback = FeedbackReview(
        investigation_id="inv-kind-demo-8088",
        rating=5,
        comment="Live Kubernetes OOMKilled diagnostic matched real cgroup limit.",
        reviewer="oncall-sre@company.com",
    )
    router.submit_feedback(feedback)
    console.print(f"[dim]Recorded 5-star user feedback for run 'inv-kind-demo-8088' (Avg Rating: {router.get_average_rating()}/5.0)[/dim]\n")


if __name__ == "__main__":
    asyncio.run(main())
