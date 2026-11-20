import { AccountLoadCard } from "@/components/operations/AccountLoadCard";
import { ForecastCard } from "@/components/operations/ForecastCard";
import { ModeCard } from "@/components/operations/ModeCard";
import { PipelineCard } from "@/components/operations/PipelineCard";
import { RepliesCard } from "@/components/operations/RepliesCard";
import { SendCard } from "@/components/operations/SendCard";
import { SendingWindowCard } from "@/components/operations/SendingWindowCard";
import { TargetCitiesCard } from "@/components/operations/TargetCitiesCard";
import { PageHeader } from "@/components/shell/PageHeader";

export default function OperationsPage() {
  return (
    <>
      <PageHeader
        title="Operations"
        description="Run the pipeline, send emails and check replies. Each button works on its own, so the rest of the page stays usable while it runs."
      />
      <div className="space-y-6">
        <ModeCard />
        <ForecastCard />
        <AccountLoadCard />
        <PipelineCard />
        <SendCard />
        <RepliesCard />
        <SendingWindowCard />
        <TargetCitiesCard />
      </div>
    </>
  );
}
