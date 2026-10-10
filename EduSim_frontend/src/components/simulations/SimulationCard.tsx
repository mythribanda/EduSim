import React from "react";

export interface SimulationCardProps {
  id: string;
  title: string;
  emoji: string;
  description: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  onClick: () => void;
}

const difficultyStyles: Record<SimulationCardProps["difficulty"], string> = {
  beginner: "bg-emerald-100 text-emerald-700 border-emerald-200",
  intermediate: "bg-orange-100 text-orange-700 border-orange-200",
  advanced: "bg-purple-100 text-purple-700 border-purple-200",
};

export const SimulationCard: React.FC<SimulationCardProps> = ({
  title,
  emoji,
  description,
  difficulty,
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="group relative flex flex-col justify-between bg-white rounded-[16px] p-6 shadow-md border border-gray-100 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl cursor-pointer select-none"
    >
      <div>
        {/* Difficulty Badge */}
        <div className="flex justify-end mb-2">
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full border capitalize ${difficultyStyles[difficulty]}`}
          >
            {difficulty}
          </span>
        </div>

        {/* Large Emoji at top center */}
        <div className="flex items-center justify-center text-[64px] leading-none my-4 transform group-hover:scale-110 transition-transform duration-300">
          {emoji}
        </div>

        {/* Title & Description */}
        <div className="text-center mt-2 space-y-2">
          <h3 className="text-[20px] font-bold text-[#1F2937] group-hover:text-[#4F8EF7] transition-colors line-clamp-1">
            {title}
          </h3>
          <p className="text-[14px] text-[#6B7280] leading-relaxed line-clamp-2">
            {description}
          </p>
        </div>
      </div>

      {/* Try It Action Button */}
      <div className="mt-6 pt-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
          className="w-full h-[48px] bg-[#4F8EF7] hover:bg-[#3b7be8] active:bg-[#2b6bd8] text-white text-[16px] font-semibold rounded-[12px] flex items-center justify-center gap-2 shadow-sm transition-colors duration-200"
        >
          <span>Try it!</span>
          <span className="text-lg transition-transform group-hover:translate-x-1 duration-200">
            &rarr;
          </span>
        </button>
      </div>
    </div>
  );
};

export default SimulationCard;
