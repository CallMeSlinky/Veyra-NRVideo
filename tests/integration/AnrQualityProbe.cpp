// SPDX-License-Identifier: GPL-3.0-only
// Offline diagnostic only: decode and compare generated frames to their endpoints.
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
}
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int W=960,H=540;
using Image=std::vector<uint8_t>;
std::vector<Image> decode(const char* path){
    AVFormatContext* format=nullptr;
    if(avformat_open_input(&format,path,nullptr,nullptr)<0)throw std::runtime_error("open failed");
    if(avformat_find_stream_info(format,nullptr)<0)throw std::runtime_error("stream info failed");
    const int stream=av_find_best_stream(format,AVMEDIA_TYPE_VIDEO,-1,-1,nullptr,0);
    if(stream<0)throw std::runtime_error("no video");
    const auto* decoder=avcodec_find_decoder(format->streams[stream]->codecpar->codec_id);
    auto* codec=avcodec_alloc_context3(decoder);
    if(!codec||avcodec_parameters_to_context(codec,format->streams[stream]->codecpar)<0)throw std::runtime_error("codec parameters failed");
    codec->thread_count=2;
    if(avcodec_open2(codec,decoder,nullptr)<0)throw std::runtime_error("decoder failed");
    auto* frame=av_frame_alloc();auto* packet=av_packet_alloc();SwsContext* scaler=nullptr;
    std::vector<Image> images;
    auto receive=[&](){int r=0;while((r=avcodec_receive_frame(codec,frame))>=0){
        scaler=sws_getCachedContext(scaler,frame->width,frame->height,AVPixelFormat(frame->format),W,H,AV_PIX_FMT_GRAY8,SWS_AREA,nullptr,nullptr,nullptr);
        if(!scaler)throw std::runtime_error("scaler failed");
        Image image(W*H);uint8_t* target[4]={image.data(),nullptr,nullptr,nullptr};int stride[4]={W,0,0,0};
        sws_scale(scaler,frame->data,frame->linesize,0,frame->height,target,stride);
        images.push_back(std::move(image));av_frame_unref(frame);
        if(images.size()>240)throw std::runtime_error("diagnostic clip exceeds 240 decoded frames");
    }if(r!=AVERROR(EAGAIN)&&r!=AVERROR_EOF)throw std::runtime_error("decode failed");};
    while(av_read_frame(format,packet)>=0){
        if(packet->stream_index==stream){if(avcodec_send_packet(codec,packet)<0)throw std::runtime_error("send failed");receive();}
        av_packet_unref(packet);
    }
    avcodec_send_packet(codec,nullptr);receive();
    sws_freeContext(scaler);av_frame_free(&frame);av_packet_free(&packet);avcodec_free_context(&codec);avformat_close_input(&format);
    return images;
}
double difference(const Image& a,const Image& b){
    double sum=0;for(size_t k=0;k<a.size();++k)sum+=std::abs(int(a[k])-int(b[k]));return sum/a.size();
}
}
int main(int argc,char** argv){
    if(argc!=4)return 2;
    try{
        if(std::string(argv[1])=="--decimate"){
            const auto frames=decode(argv[2]);FILE* file=nullptr;fopen_s(&file,argv[3],"wb");
            if(!file)throw std::runtime_error("cannot create diagnostic fixture");
            std::fprintf(file,"YUV4MPEG2 W%d H%d F15:1 Ip A1:1 C420jpeg XCOLORRANGE=FULL\n",W,H);
            const std::vector<uint8_t> chroma(W*H/2,128);
            for(size_t i=0;i<frames.size();i+=2){std::fwrite("FRAME\n",1,6,file);std::fwrite(frames[i].data(),1,frames[i].size(),file);std::fwrite(chroma.data(),1,chroma.size(),file);}
            std::fclose(file);return 0;
        }
        if(std::string(argv[1])=="--holdout"){
            const auto truth=decode(argv[2]),interpolated=decode(argv[3]);
            if(truth.size()!=interpolated.size()||truth.size()<6)throw std::runtime_error("holdout length mismatch");
            double error=0,held=0,blend=0,real=0;unsigned count=0;
            for(size_t i=1;i+1<truth.size();i+=2){
                error+=difference(truth[i],interpolated[i]);held+=difference(truth[i],truth[i-1]);
                for(size_t k=0;k<truth[i].size();++k)blend+=std::abs(truth[i][k]-(truth[i-1][k]+truth[i+1][k])*0.5)/truth[i].size();
                real+=difference(truth[i-1],interpolated[i-1]);++count;
            }
            std::printf("{\"heldOutFrames\":%u,\"generatedGroundTruthMae\":%.6f,\"sourceHoldGroundTruthMae\":%.6f,\"linearBlendGroundTruthMae\":%.6f,\"realFrameAlignmentMae\":%.6f}\n",count,error/count,held/count,blend/count,real/count);
            return 0;
        }
        const auto original=decode(argv[1]),generated=decode(argv[2]);const unsigned multiplier=std::stoul(argv[3]);
        if(multiplier<2||multiplier>6||generated.size()!=original.size()*multiplier)throw std::runtime_error("frame count mismatch");
        double realError=0;for(size_t i=0;i<original.size();++i)realError+=difference(original[i],generated[i*multiplier]);
        double nearestRatio=0,blendError=0;unsigned measured=0;
        for(size_t i=2;i<original.size();++i){
            const auto& a=original[i-1];const auto& b=original[i];const double ab=difference(a,b);
            if(ab<0.25)continue;
            for(unsigned sub=1;sub<multiplier;++sub){
                const auto& g=generated[(i-1)*multiplier+sub];
                nearestRatio+=std::min(difference(a,g),difference(b,g))/ab;
                double error=0;const double t=double(sub)/multiplier;
                for(size_t k=0;k<g.size();++k)error+=std::abs(g[k]-(a[k]*(1-t)+b[k]*t));
                blendError+=error/g.size();++measured;
            }
        }
        std::printf("{\"sourceFrames\":%zu,\"outputFrames\":%zu,\"measuredGeneratedFrames\":%u,\"realFrameAlignmentMae\":%.6f,\"nearestEndpointDifferenceRatio\":%.6f,\"linearBlendMae\":%.6f}\n",original.size(),generated.size(),measured,realError/original.size(),measured?nearestRatio/measured:0,measured?blendError/measured:0);
        return measured?0:1;
    }catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
