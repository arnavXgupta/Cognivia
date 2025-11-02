import { ChevronDown, ChevronUp, Calendar, Clock, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';

export const StudyPlanPanel = ({ studyPlan, resources = [], onGenerate, isGenerating = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasResources = resources && resources.length > 0;
  const hasPlan = studyPlan && studyPlan.weeks && studyPlan.weeks.length > 0;

  if (!hasPlan) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            AI Study Plan
          </h3>
          {hasResources && onGenerate && (
            <Button
              size="sm"
              variant="secondary"
              onClick={onGenerate}
              disabled={isGenerating}
              icon={Sparkles}
            >
              {isGenerating ? 'Generating...' : 'Generate Plan'}
            </Button>
          )}
        </div>
        <p className="text-white/60 text-sm">
          {hasResources
            ? 'Click "Generate Plan" to create a personalized study plan from your resources'
            : 'Upload resources to generate a personalized study plan'}
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Calendar className="w-5 h-5" />
          AI Study Plan
        </h3>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-white/60" />
        ) : (
          <ChevronDown className="w-5 h-5 text-white/60" />
        )}
      </div>

      {isExpanded && (
        <div className="mt-4 space-y-4">
          {studyPlan.weeks.map((week, index) => (
            <div
              key={index}
              className="border border-white/10 rounded-lg p-4 bg-white/5"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-white font-medium">Week {week.week}</h4>
                <div className="flex items-center gap-1 text-white/60 text-sm">
                  <Clock className="w-4 h-4" />
                  <span>{week.hours}h</span>
                </div>
              </div>
              <ul className="space-y-2">
                {week.topics.map((topic, topicIndex) => (
                  <li
                    key={topicIndex}
                    className="flex items-start gap-2 text-white/80 text-sm"
                  >
                    <span className="text-white/40 mt-1">•</span>
                    <span>{topic}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
