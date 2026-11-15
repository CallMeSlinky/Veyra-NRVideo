#pragma once
#include <cstdint>
#include <string_view>

namespace veyra::sink {
// Stable UI/settings IDs. Keep the legacy HEVC boolean readable by old callers.
enum class VideoCodec : uint32_t { H264=0, Hevc=1, Av1=2 };
constexpr bool validVideoCodec(VideoCodec codec) { return uint32_t(codec)<=2; }
constexpr VideoCodec selectedVideoCodec(VideoCodec codec,bool legacyHevc=false) {
    return codec==VideoCodec::H264&&legacyHevc?VideoCodec::Hevc:codec;
}
constexpr VideoCodec recordingVideoCodec(VideoCodec codec,bool hdr,uint32_t width,uint32_t height) {
    return codec==VideoCodec::H264&&(hdr||width>4096||height>4096)?VideoCodec::Hevc:codec;
}
constexpr std::string_view videoCodecName(VideoCodec codec) {
    switch(codec) {
    case VideoCodec::H264:return "H.264";
    case VideoCodec::Hevc:return "H.265 / HEVC";
    case VideoCodec::Av1:return "AV1";
    }
    return "unknown";
}
constexpr std::wstring_view videoCodecWideName(VideoCodec codec) {
    switch(codec) {
    case VideoCodec::H264:return L"H.264";
    case VideoCodec::Hevc:return L"H.265 / HEVC";
    case VideoCodec::Av1:return L"AV1";
    }
    return L"unknown";
}
}
