export const GENRES = {
    pop: { name: "Pop", icon: "🎤", color: "#FF6B9D", subgenres: [
        { name: "Modern Pop", query: "pop hits 2024" },
        { name: "Classic Pop", query: "80s 90s pop hits" },
        { name: "K-Pop", query: "kpop hits" }
    ]},
    hiphop: { name: "Hip-Hop", icon: "🧢", color: "#FFD93D", subgenres: [
        { name: "Trap", query: "trap music hits" },
        { name: "Old School", query: "90s hip hop classics" },
        { name: "Melodic Rap", query: "melodic rap" }
    ]},
    electronic: { name: "Electronic", icon: "🎧", color: "#9B59B6", subgenres: [
        { name: "House", query: "house music" },
        { name: "Techno", query: "techno music" },
        { name: "DnB", query: "drum and bass liquid" },
        { name: "Phonk", query: "drift phonk" }
    ]},
    rock: { name: "Rock", icon: "🎸", color: "#E74C3C", subgenres: [
        { name: "Classic Rock", query: "classic rock hits" },
        { name: "Alternative", query: "alternative rock" },
        { name: "Metal", query: "heavy metal" },
        { name: "Russian Rock", query: "russian rock classics" }
    ]},
    lofi: { name: "Lofi & Chill", icon: "☕", color: "#00F2FF", subgenres: [
        { name: "Lofi Hip Hop", query: "lofi hip hop radio" },
        { name: "Synthwave", query: "synthwave retro wave" },
        { name: "Ambient", query: "ambient space music" }
    ]}
};

export const MOODS = [
    { name: "🔥 Viral", query: "tiktok viral hits 2024" },
    { name: "💪 Workout", query: "workout phonk" },
    { name: "🚗 Drive", query: "night drive music" },
    { name: "🌌 Space", query: "space ambient" }
];