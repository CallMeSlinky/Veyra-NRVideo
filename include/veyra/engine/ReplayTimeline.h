#pragma once
#include <cstdint>
#include <mutex>
#include <optional>

namespace veyra::engine {
// Replay time advances only while a source plays. Audio, video and save
// requests share this mapping so a pause cannot age the picture out of a clip.
class ReplayTimeline {
public:
    explicit ReplayTimeline(int64_t now):pausedAt_(now),resumedAt_(now){}
    void setPlaying(bool playing,int64_t now){
        std::lock_guard lock(mutex_);
        if(playing==playing_)return;
        if(playing){omitted_+=now-pausedAt_;resumedAt_=now;}
        else pausedAt_=now;
        playing_=playing;
    }
    bool playing()const{std::lock_guard lock(mutex_);return playing_;}
    int64_t now(int64_t raw)const{
        std::lock_guard lock(mutex_);return (playing_?raw:pausedAt_)-omitted_;
    }
    std::optional<int64_t> sample(int64_t raw)const{
        std::lock_guard lock(mutex_);
        // Reject delayed audio from before the resume boundary as well as
        // audio/microphone callbacks arriving during the pause.
        if(!playing_||raw<resumedAt_)return std::nullopt;
        return raw-omitted_;
    }
private:
    mutable std::mutex mutex_;
    bool playing_=false;
    int64_t pausedAt_,resumedAt_,omitted_=0;
};
}
