// SPDX-License-Identifier: GPL-3.0-only
// Decode delivered export bytes independently of the product's counters.
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/pixdesc.h>
}
#include <cstdio>
#include <algorithm>
#include <set>
#include <cstdint>
int main(int argc,char** argv){
    if(argc!=2)return 2;
    AVFormatContext* format=nullptr;if(avformat_open_input(&format,argv[1],nullptr,nullptr)<0)return 2;
    if(avformat_find_stream_info(format,nullptr)<0)return 2;
    const int stream=av_find_best_stream(format,AVMEDIA_TYPE_VIDEO,-1,-1,nullptr,0);if(stream<0)return 2;
    auto* decoder=avcodec_find_decoder(format->streams[stream]->codecpar->codec_id);if(!decoder)return 2;
    auto* codec=avcodec_alloc_context3(decoder);if(!codec)return 2;
    if(avcodec_parameters_to_context(codec,format->streams[stream]->codecpar)<0||avcodec_open2(codec,decoder,nullptr)<0)return 2;
    AVFrame* frame=av_frame_alloc();AVPacket* packet=av_packet_alloc();if(!frame||!packet)return 2;
    unsigned frames=0,keys=0;std::set<uint64_t> hashes;
    int64_t previousPts=AV_NOPTS_VALUE,maximumGapUs=0;
    auto receive=[&](){int r=0;while((r=avcodec_receive_frame(codec,frame))>=0){
        if(frame->best_effort_timestamp!=AV_NOPTS_VALUE){
            const int64_t pts=av_rescale_q(frame->best_effort_timestamp,format->streams[stream]->time_base,AVRational{1,1000000});
            if(previousPts!=AV_NOPTS_VALUE)maximumGapUs=std::max(maximumGapUs,pts-previousPts);
            previousPts=pts;
        }
        uint64_t hash=1469598103934665603ull;
        for(int y=0;y<frame->height;++y)for(int x=0;x<frame->width;++x)hash=(hash^frame->data[0][y*frame->linesize[0]+x])*1099511628211ull;
        hashes.insert(hash);++frames;av_frame_unref(frame);
    }return r==AVERROR(EAGAIN)||r==AVERROR_EOF;};
    int result=0;
    while(av_read_frame(format,packet)>=0){
        if(packet->stream_index==stream&&(packet->flags&AV_PKT_FLAG_KEY))++keys;
        if(packet->stream_index==stream&&(avcodec_send_packet(codec,packet)<0||!receive())){result=1;break;}
        av_packet_unref(packet);
    }
    avcodec_send_packet(codec,nullptr);if(!receive())result=1;
    const AVRational fps=av_guess_frame_rate(format,format->streams[stream],nullptr);
    const double duration=format->duration==AV_NOPTS_VALUE?0:double(format->duration)/1000000;
    const auto* pixels=av_pix_fmt_desc_get(codec->pix_fmt);
    std::printf("{\"frames\":%u,\"distinctLumaFrames\":%zu,\"width\":%d,\"height\":%d,\"fpsNumerator\":%d,\"fpsDenominator\":%d,\"maxVideoPtsGapUs\":%lld,\"durationSeconds\":%.6f,\"codec\":\"%s\",\"bitDepth\":%d,\"keyframes\":%u,\"primaries\":%d,\"transfer\":%d,\"matrix\":%d}\n",frames,hashes.size(),codec->width,codec->height,fps.num,fps.den,static_cast<long long>(maximumGapUs),duration,avcodec_get_name(codec->codec_id),pixels?pixels->comp[0].depth:0,keys,int(codec->color_primaries),int(codec->color_trc),int(codec->colorspace));
    av_packet_free(&packet);av_frame_free(&frame);avcodec_free_context(&codec);avformat_close_input(&format);
    return result;
}
