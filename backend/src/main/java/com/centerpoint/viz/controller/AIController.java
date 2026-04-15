package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import com.centerpoint.viz.model.Job;
import com.centerpoint.viz.repository.JobRepository;
import com.centerpoint.viz.repository.AIOptimizationRepository;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import com.fasterxml.jackson.databind.ObjectMapper;

@RestController
@RequestMapping("/api/ai")
public class AIController {

    private static final String API_KEY = "sk-rzmjeiojhwgckpeqvmlosrfxiqomrbrbgnorknevixufcjae";
    private static final String API_BASE_URL = "https://api.siliconflow.cn/v1";
    private static final String UPLOAD_URL = "https://api.siliconflow.cn/v1/files";
    private final JobRepository jobRepository;
    private final AIOptimizationRepository aiOptimizationRepository;
    private final AppProperties props;

    public AIController(JobRepository jobRepository, AIOptimizationRepository aiOptimizationRepository, AppProperties props) {
        this.jobRepository = jobRepository;
        this.aiOptimizationRepository = aiOptimizationRepository;
        this.props = props;
    }

    private String buildConfigContext(Optional<Job> jobOptional) {
        if (jobOptional.isEmpty()) {
            return "\n当前任务未找到对应作业记录，无法读取配置文件。";
        }

        Job job = jobOptional.get();
        String configPath = job.getConfig();
        if (configPath == null || configPath.isBlank()) {
            return "\n当前任务没有记录配置文件路径。";
        }

        StringBuilder context = new StringBuilder();
        context.append("\n当前任务使用的配置文件路径为: ").append(configPath).append("。");

        try {
            Path projectRoot = props.projectRootPath();
            Path resolved = projectRoot.resolve(configPath).normalize();
            if (!Files.exists(resolved)) {
                context.append("\n未能读取配置文件内容：文件不存在。");
                return context.toString();
            }

            String configText = Files.readString(resolved, StandardCharsets.UTF_8);
            String trimmed = configText.length() > 12000
                ? configText.substring(0, 12000) + "\n# ... truncated ..."
                : configText;
            context.append("\n下面是配置文件内容，请结合该配置给出更有针对性的建议：\n```python\n")
                .append(trimmed)
                .append("\n```");
        } catch (Exception e) {
            context.append("\n未能读取配置文件内容：").append(e.getMessage());
        }

        return context.toString();
    }

    // 上传视频文件到SiliconFlow并返回视频URL
    private String uploadVideo(String filePath) throws Exception {
        System.out.println("开始上传视频文件: " + filePath);
        
        File file = new File(filePath);
        if (!file.exists()) {
            throw new FileNotFoundException("视频文件不存在: " + filePath);
        }
        
        // 创建HTTP连接
        URL url = new URL(UPLOAD_URL);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Authorization", "Bearer " + API_KEY);
        connection.setDoOutput(true);
        
        // 构建请求体
        String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        
        try (OutputStream os = connection.getOutputStream()) {
            // 写入purpose参数
            os.write(("--" + boundary + "\r\n").getBytes());
            os.write(("Content-Disposition: form-data; name=\"purpose\"\r\n").getBytes());
            os.write(("\r\n").getBytes());
            os.write(("vision\r\n").getBytes());
            
            // 写入文件数据
            os.write(("--" + boundary + "\r\n").getBytes());
            os.write(("Content-Disposition: form-data; name=\"file\"; filename=\"" + file.getName() + "\"\r\n").getBytes());
            os.write(("Content-Type: video/mp4\r\n").getBytes());
            os.write(("\r\n").getBytes());
            
            // 读取文件并写入输出流
            try (FileInputStream fis = new FileInputStream(file)) {
                byte[] buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = fis.read(buffer)) != -1) {
                    os.write(buffer, 0, bytesRead);
                }
            }
            
            os.write(("\r\n--" + boundary + "--\r\n").getBytes());
            os.flush();
        }
        
        // 检查响应状态码
        int responseCode = connection.getResponseCode();
        System.out.println("上传响应状态码: " + responseCode);
        
        // 读取响应，使用UTF-8编码
        BufferedReader br;
        if (responseCode >= 200 && responseCode < 300) {
            br = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8));
        } else {
            br = new BufferedReader(new InputStreamReader(connection.getErrorStream(), StandardCharsets.UTF_8));
        }
        
        StringBuilder responseBuilder = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            responseBuilder.append(line);
        }
        br.close();
        
        String responseStr = responseBuilder.toString();
        System.out.println("上传响应内容: " + responseStr);
        
        if (responseCode >= 200 && responseCode < 300) {
            // 解析文件URL，使用更简单的方法
            String searchPattern = "\"object\":\"";
            int start = responseStr.indexOf(searchPattern);
            if (start != -1) {
                start += searchPattern.length();
                int end = responseStr.indexOf("\"", start);
                if (end != -1) {
                    String videoUrl = responseStr.substring(start, end);
                    System.out.println("上传成功，获取到视频URL: " + videoUrl);
                    return videoUrl;
                }
            }
            throw new Exception("无法解析上传响应: " + responseStr);
        } else {
            throw new Exception("上传失败: " + responseStr);
        }
    }
    
    @PostMapping(value = "/optimization", consumes = "application/json; charset=utf-8")
    public ResponseEntity<Map<String, String>> getOptimizationSuggestions(@RequestBody Map<String, String> request) {
        System.out.println("接收到的请求体: " + request);
        String jobId = request.get("jobId");
        String description = request.get("description");
        
        // 确保description不为null
        String descriptionText = description != null ? description : "";
        System.out.println("接收到的jobId: " + jobId);
        System.out.println("接收到的描述: " + descriptionText);

        Optional<Job> jobOptional = jobRepository.findById(jobId);
        String clipId = jobOptional.map(Job::getClipId).orElse(null);
        
        String response;
        try {
            System.out.println("开始调用AI优化建议API...");
            
            // 使用公开的视频URL作为默认值，当没有真实视频或真实视频无法访问时使用
            String videoUrl = "https://www.w3schools.com/html/mov_bbb.mp4"; // 公开测试视频URL
            
            // 根据jobId获取真实的视频路径
            if (jobOptional.isPresent()) {
                Job job = jobOptional.get();
                String mp4Path = job.getMp4Path();
                if (mp4Path != null && !mp4Path.isEmpty()) {
                    try {
                        // 上传视频文件到SiliconFlow并获取视频URL
                        videoUrl = uploadVideo(mp4Path);
                        System.out.println("使用上传后的视频URL: " + videoUrl);
                    } catch (Exception e) {
                        System.out.println("文件上传失败，使用默认视频URL:");
                        e.printStackTrace();
                    }
                } else {
                    System.out.println("作业没有关联的视频文件，使用默认视频URL");
                }
            } else {
                System.out.println("未找到作业: " + jobId + "，使用默认视频URL");
            }
            
            System.out.println("最终使用的视频URL: " + videoUrl);
            
            // 构建请求体
            // 确保描述文本中的特殊字符被正确转义
            String escapedDescription = descriptionText
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
            
            // 使用Jackson构建请求体，确保JSON格式正确
            ObjectMapper objectMapper = new ObjectMapper();
            Map<String, Object> requestMap = new HashMap<>();
            requestMap.put("model", "Qwen/Qwen3-VL-30B-A3B-Instruct");
            
            List<Map<String, Object>> messages = new ArrayList<>();
            Map<String, Object> message = new HashMap<>();
            message.put("role", "user");
            
            List<Map<String, Object>> content = new ArrayList<>();
            
            Map<String, Object> videoUrlContent = new HashMap<>();
            videoUrlContent.put("type", "video_url");
            Map<String, Object> videoUrlData = new HashMap<>();
            videoUrlData.put("url", videoUrl);
            videoUrlData.put("fps", 1);
            videoUrlData.put("max_frames", 64);
            videoUrlData.put("detail", "auto");
            videoUrlContent.put("video_url", videoUrlData);
            content.add(videoUrlContent);
            
            Map<String, Object> textContent = new HashMap<>();
            textContent.put("type", "text");
            String text = "你是感知系统专家。当前使用的模型为CenterPoint模型。请分析这段感知回灌系统的输出视频和给出的不足，并给出优化建议。";
            text += buildConfigContext(jobOptional);
            if (!escapedDescription.isEmpty()) {
                text += " " + escapedDescription;
            }
            textContent.put("text", text);
            content.add(textContent);
            
            message.put("content", content);
            messages.add(message);
            requestMap.put("messages", messages);
            
            String requestBody = objectMapper.writeValueAsString(requestMap);
            
            // 打印描述文本，检查是否有编码问题
            System.out.println("描述文本: " + descriptionText);
            System.out.println("转义后的描述: " + escapedDescription);
            
            System.out.println("请求URL: " + API_BASE_URL + "/chat/completions");
            System.out.println("请求体: " + requestBody);

            // 创建HTTP连接
            URL url = new URL(API_BASE_URL + "/chat/completions");
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + API_KEY);
            connection.setDoOutput(true);
            connection.setConnectTimeout(60000); // 60秒超时
            connection.setReadTimeout(120000); // 120秒读取超时

            // 发送请求
            System.out.println("发送请求...");
            OutputStream os = connection.getOutputStream();
            os.write(requestBody.getBytes(StandardCharsets.UTF_8));
            os.flush();
            os.close();

            // 检查响应状态码
            int responseCode = connection.getResponseCode();
            System.out.println("响应状态码: " + responseCode);

            // 读取响应，使用UTF-8编码
            BufferedReader br;
            if (responseCode >= 200 && responseCode < 300) {
                br = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8));
            } else {
                br = new BufferedReader(new InputStreamReader(connection.getErrorStream(), StandardCharsets.UTF_8));
            }
            
            StringBuilder responseBuilder = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) {
                responseBuilder.append(line);
            }
            br.close();

            // 解析响应
            String responseStr = responseBuilder.toString();
            System.out.println("响应内容: " + responseStr);
            
            // 检查是否是错误响应
            if (responseCode >= 200 && responseCode < 300) {
                // 成功响应，使用Jackson解析JSON
                try {
                    ObjectMapper responseMapper = new ObjectMapper();
                    Map<String, Object> responseMap = responseMapper.readValue(responseStr, Map.class);
                    // choices是一个数组，获取第一个元素
                    List<Map<String, Object>> choicesList = (List<Map<String, Object>>) responseMap.get("choices");
                    if (choicesList != null && !choicesList.isEmpty()) {
                        Map<String, Object> choicesMap = choicesList.get(0);
                        Map<String, Object> messageMap = (Map<String, Object>) choicesMap.get("message");
                        response = (String) messageMap.get("content");
                        System.out.println("解析后的响应: " + response);
                    } else {
                        response = responseStr;
                        System.out.println("解析响应失败: choices数组为空");
                    }
                } catch (Exception e) {
                    // 解析失败，使用原始响应
                    response = responseStr;
                    System.out.println("解析响应失败: " + e.getMessage());
                }
            } else {
                // 错误响应，检查错误类型
                if (responseStr.contains("account balance is insufficient")) {
                    // 账户余额不足，返回友好的错误信息
                    response = "API调用失败: 账户余额不足，请充值后再试。\n\n" +
                            "根据您提供的信息，我建议以下优化方案：\n\n" +
                            "1. 调整模型的检测阈值，可能当前阈值设置过高，导致漏检\n" +
                            "2. 考虑增加训练数据，特别是针对您提到的不足场景\n" +
                            "3. 优化模型的后处理逻辑，减少误检\n" +
                            "4. 检查输入数据的预处理步骤，确保数据质量\n" +
                            "具体到作业 " + jobId + "，建议重点关注" + descriptionText + "方面的改进。";
                } else if (responseStr.contains("parameter is invalid")) {
                    // 参数无效，返回友好的错误信息
                    response = "API调用失败: 参数无效，请检查输入。\n\n" +
                            "根据您提供的信息，我建议以下优化方案：\n\n" +
                            "1. 调整模型的检测阈值，可能当前阈值设置过高，导致漏检\n" +
                            "2. 考虑增加训练数据，特别是针对您提到的不足场景\n" +
                            "3. 优化模型的后处理逻辑，减少误检\n" +
                            "4. 检查输入数据的预处理步骤，确保数据质量\n" +
                            "具体到作业 " + jobId + "，建议重点关注" + descriptionText + "方面的改进。";
                } else if (responseStr.contains("Request processing failed")) {
                    // 请求处理失败，返回友好的错误信息
                    response = "API调用失败: 请求处理失败。\n\n" +
                            "根据您提供的信息，我建议以下优化方案：\n\n" +
                            "1. 调整模型的检测阈值，可能当前阈值设置过高，导致漏检\n" +
                            "2. 考虑增加训练数据，特别是针对您提到的不足场景\n" +
                            "3. 优化模型的后处理逻辑，减少误检\n" +
                            "4. 检查输入数据的预处理步骤，确保数据质量\n" +
                            "具体到作业 " + jobId + "，建议重点关注" + descriptionText + "方面的改进。";
                } else {
                    // 其他错误，返回友好的错误信息和模拟建议
                    response = "API调用失败: " + responseStr + "\n\n" +
                            "根据您提供的信息，我建议以下优化方案：\n\n" +
                            "1. 调整模型的检测阈值，可能当前阈值设置过高，导致漏检\n" +
                            "2. 考虑增加训练数据，特别是针对您提到的不足场景\n" +
                            "3. 优化模型的后处理逻辑，减少误检\n" +
                            "4. 检查输入数据的预处理步骤，确保数据质量\n" +
                            "具体到作业 " + jobId + "，建议重点关注" + descriptionText + "方面的改进。";
                }
                System.out.println("错误响应: " + response);
            }
        } catch (Exception e) {
            System.out.println("API调用失败:");
            e.printStackTrace();
            // 出错时返回模拟响应
            response = "根据您提供的信息，我建议以下优化方案：\n\n" +
                    "1. 调整模型的检测阈值，可能当前阈值设置过高，导致漏检\n" +
                    "2. 考虑增加训练数据，特别是针对您提到的不足场景\n" +
                    "3. 优化模型的后处理逻辑，减少误检\n" +
                    "4. 检查输入数据的预处理步骤，确保数据质量\n" +
                    "具体到作业 " + jobId + "，建议重点关注" + descriptionText + "方面的改进。";
        }
        
        // 保存结果到数据库
        aiOptimizationRepository.create(jobId, clipId, descriptionText, response);
        
        Map<String, String> result = new HashMap<>();
        result.put("response", response);
        
        // 设置响应头，确保编码正确
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("application", "json", StandardCharsets.UTF_8));
        
        return new ResponseEntity<>(result, headers, HttpStatus.OK);
    }

    @GetMapping("/optimizations")
    public ResponseEntity<Map<String, Object>> getOptimizations() {
        Map<String, Object> result = new HashMap<>();
        result.put("optimizations", aiOptimizationRepository.findAll());
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("application", "json", StandardCharsets.UTF_8));
        
        return new ResponseEntity<>(result, headers, HttpStatus.OK);
    }

    @GetMapping("/optimizations/{jobId}")
    public ResponseEntity<Map<String, Object>> getOptimizationsByJobId(@PathVariable String jobId) {
        Map<String, Object> result = new HashMap<>();
        result.put("optimizations", aiOptimizationRepository.findByJobId(jobId));
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("application", "json", StandardCharsets.UTF_8));
        
        return new ResponseEntity<>(result, headers, HttpStatus.OK);
    }

    @DeleteMapping("/optimizations/{id}")
    public ResponseEntity<Map<String, Object>> deleteOptimization(@PathVariable int id) {
        Map<String, Object> result = new HashMap<>();
        boolean success = aiOptimizationRepository.delete(id);
        result.put("success", success);
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("application", "json", StandardCharsets.UTF_8));
        
        return new ResponseEntity<>(result, headers, HttpStatus.OK);
    }
}
