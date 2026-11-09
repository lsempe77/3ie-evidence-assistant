"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Settings } from "lucide-react";
import type { AnswerStyle } from "@/types";

export interface SearchSettings {
  relevanceThreshold: number;
  maxStudies: number;
  answerStyle: AnswerStyle;
  useReranking: boolean;
  minConfidence: "all" | "medium" | "high";
  includeOlderStudies: boolean;
  yearCutoff: number;
  /** Write the answer with the stronger model (slower, costs more). */
  deepAnswer: boolean;
}

// relevanceThreshold, maxStudies and answerStyle only affect the old answer pipeline
// (ANSWER_PIPELINE=agent). The default pipeline reads every relevant study, so they are
// not shown. See docs/MODEL_REVIEW_2026-11.md.
const defaultSettings: SearchSettings = {
  relevanceThreshold: 0.2,
  maxStudies: 10,
  answerStyle: "executive",
  useReranking: true,
  minConfidence: "all",
  includeOlderStudies: true,
  yearCutoff: 2010,
  deepAnswer: false,
};

interface SettingsDrawerProps {
  settings: SearchSettings;
  onSettingsChange: (settings: SearchSettings) => void;
}

export function SettingsDrawer({ settings, onSettingsChange }: SettingsDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [deepAnswer, setDeepAnswer] = useState(settings.deepAnswer);

  const handleOpenChange = (open: boolean) => {
    if (open) setDeepAnswer(settings.deepAnswer);
    setIsOpen(open);
  };

  const handleApply = () => {
    onSettingsChange({ ...settings, deepAnswer });
    setIsOpen(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Answer settings">
          <Settings aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Answer settings</DialogTitle>
          <DialogDescription>
            Every answer is written from all the studies in this collection that address your
            question.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-start justify-between gap-4 py-4">
          <div className="space-y-1">
            <Label htmlFor="setting-deep">Deeper answer</Label>
            <p className="text-body text-ink-muted">
              Uses a stronger model to write the answer. Slower, and best for questions that
              weigh many studies against each other.
            </p>
          </div>
          <Switch id="setting-deep" checked={deepAnswer} onCheckedChange={setDeepAnswer} />
        </div>

        <DialogFooter>
          <Button onClick={handleApply}>Apply settings</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { defaultSettings };
