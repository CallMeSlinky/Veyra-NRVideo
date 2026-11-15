#pragma once
#include "veyra/sink/VideoCodec.h"
#include <ffnvcodec/nvEncodeAPI.h>
#include <algorithm>
#include <vector>

namespace veyra::sink {
inline GUID nvencCodecGuid(VideoCodec codec) {
    return codec==VideoCodec::Av1?NV_ENC_CODEC_AV1_GUID:codec==VideoCodec::Hevc?NV_ENC_CODEC_HEVC_GUID:NV_ENC_CODEC_H264_GUID;
}
// Query the opened device, rather than guessing from its marketing name.
inline bool nvencSupportsCodec(NV_ENCODE_API_FUNCTION_LIST& api,void* encoder,const GUID& codec) {
    uint32_t count=0,actual=0;
    if(api.nvEncGetEncodeGUIDCount(encoder,&count)!=NV_ENC_SUCCESS||!count)return false;
    std::vector<GUID> codecs(count);
    if(api.nvEncGetEncodeGUIDs(encoder,codecs.data(),count,&actual)!=NV_ENC_SUCCESS)return false;
    return std::any_of(codecs.begin(),codecs.begin()+std::min(count,actual),[&](const GUID& found){return IsEqualGUID(found,codec);});
}
inline void configureNvencAv1(NV_ENC_CONFIG& cfg,bool hdr) {
    cfg.profileGUID=NV_ENC_AV1_PROFILE_MAIN_GUID;
    auto& av1=cfg.encodeCodecConfig.av1Config;
    av1.idrPeriod=cfg.gopLength;
    av1.repeatSeqHdr=1;
    av1.chromaFormatIDC=1;
    av1.inputBitDepth=av1.outputBitDepth=hdr?NV_ENC_BIT_DEPTH_10:NV_ENC_BIT_DEPTH_8;
    av1.colorRange=0;
    av1.colorPrimaries=hdr?NV_ENC_VUI_COLOR_PRIMARIES_BT2020:NV_ENC_VUI_COLOR_PRIMARIES_BT709;
    av1.transferCharacteristics=hdr?NV_ENC_VUI_TRANSFER_CHARACTERISTIC_SMPTE2084:NV_ENC_VUI_TRANSFER_CHARACTERISTIC_BT709;
    av1.matrixCoefficients=hdr?NV_ENC_VUI_MATRIX_COEFFS_BT2020_NCL:NV_ENC_VUI_MATRIX_COEFFS_BT709;
}
}
