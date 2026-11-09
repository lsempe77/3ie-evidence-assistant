"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Settings, RotateCcw } from "lucide-react";
import type { AnswerStyle } from "@/types";

export interface SearchSettings {
  relevanceThreshold: number;
  maxStudies: number;
  answerStyle: AnswerStyle;
  useReranking: boolean;
  minConfidence: "all" | "medium" | "high";
  includeOlderStudies: boolean;
  yearCutoff: number;
}

const defaultSettings: SearchSettings = {
  relevanceThreshold: 0.2, // rerank scores rarely exceed 0.7; see src/retrieval/selection.py
  maxStudies: 10,
  answerStyle: "executive",
  useReranking: true,
  minConfidence: "all",
  includeOlderStudies: true,
  yearCutoff: 2010,
};

interface SettingsDrawerProps {
  settings: SearchSettings;
  onSettingsChange: (settings: SearchSettings) => void;
}

export function SettingsDrawer({ settings, onSettingsChange }: SettingsDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [localSettings, setLocalSettings] = useState<SearchSettings>(settings);

  const handleChange = <K extends keyof SearchSettings>(key: K, value: SearchSettings[K]) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleApply = () => {
    onSettingsChange(localSettings);
    setIsOpen(false);
  };

  const handleReset = () => {
    setLocalSettings(defaultSettings);
  };

  const handleSliderChange = (key: "relevanceThreshold" | "maxStudies" | "yearCutoff", divisor = 1) => 
    (values: number[]) => handleChange(key, values[0] / divisor);
  
  const handleSelectChange = <T extends string>(key: keyof SearchSettings) =>
    (value: T) => handleChange(key, value as SearchSettings[typeof key]);
  

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Answer settings">
          <Settings aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Answer settings</DialogTitle>
          <DialogDescription>
            Choose how many studies an answer draws on and how it is written.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Relevance Threshold */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="setting-relevance">Minimum relevance</Label>
              <span className="tabular text-sm text-muted-foreground">
                {(localSettings.relevanceThreshold * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              id="setting-relevance"
              value={[localSettings.relevanceThreshold * 100]}
              onValueChange={handleSliderChange("relevanceThreshold", 100)}
              min={0}
              max={100}
              step={5}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Studies that match the question less closely than this are left out.
            </p>
          </div>

          {/* Max Studies */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="setting-max-studies">Most studies to use</Label>
              <span className="tabular text-sm text-muted-foreground">
                {localSettings.maxStudies}
              </span>
            </div>
            <Slider
              id="setting-max-studies"
              value={[localSettings.maxStudies]}
              onValueChange={handleSliderChange("maxStudies")}
              min={3}
              max={25}
              step={1}
              className="w-full"
            />
          </div>

          {/* Answer Style */}
          <div className="space-y-2">
            <Label htmlFor="setting-style">Answer style</Label>
            <Select
              value={localSettings.answerStyle}
              onValueChange={handleSelectChange<AnswerStyle>("answerStyle")}
            >
              <SelectTrigger id="setting-style">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="executive">Executive summary</SelectItem>
                <SelectItem value="research">Detailed research</SelectItem>
                <SelectItem value="policy">Policy brief</SelectItem>
                <SelectItem value="citations">Sources only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={handleReset} className="gap-1">
            <RotateCcw className="h-3 w-3" />
            Reset
          </Button>
          <Button onClick={handleApply}>
            Apply settings
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { defaultSettings };
