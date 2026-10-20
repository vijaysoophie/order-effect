using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class PsychophysicsExperiment : MonoBehaviour
{
    public GameObject square;
    public GameObject background;
    public TMP_Text instructionText;
    public string colorInputFileName = "colors.txt";  // Input file for colors to display
    public string recordInputFileName = "record_colors.txt"; // Input file for colors to record
    public string outputFileName = "results.txt"; // Output file name

    private List<Trial> trials = new List<Trial>();
    private List<Trial> recordTrials = new List<Trial>(); // For recording colors
    private int currentTrialIndex = 0;
    public float trialDuration = 0.300f; // Duration for which the trial is displayed
    public float ISI = 0.600f; // Duration for which the trial is displayed
    public float ITI = 0.600f; // Duration for which the trial is displayed
    

    // Audio feedback
    private AudioSource beepAudioSource; // For the sinusoidal beep
    private AudioSource noiseAudioSource; // For the noise
    private float beepFrequency = 440f; // Frequency of the beep (440Hz = A4)
    private float samplingFrequency = 48000f; // Standard sampling rate

    // Experiment state
    private bool experimentStarted = false; // Tracks whether the experiment has started

    void Start()
    {
        ParseCommandLineArguments();

        // Initialize audio sources
        beepAudioSource = gameObject.AddComponent<AudioSource>();
        noiseAudioSource = gameObject.AddComponent<AudioSource>();

        // Load trials from color input file (for display)
        if (!string.IsNullOrEmpty(colorInputFileName))
        {
            LoadTrials(colorInputFileName, false);
        }
        else
        {
            Debug.LogError("Color input file name is not set.");
            return;
        }

        // Load trials from record input file (for recording)
        if (!string.IsNullOrEmpty(recordInputFileName))
        {
            LoadTrials(recordInputFileName, true);
        }
        else
        {
            Debug.LogError("Record input file name is not set.");
            return;
        }

        // Initialize results file
        if (!string.IsNullOrEmpty(outputFileName))
        {
            if (File.Exists(outputFileName))
            {
                File.Delete(outputFileName);
            }
        }
        else
        {
            Debug.LogError("Output file name is not set.");
            return;
        }
        
        // Hide squares and backgrounds initially
        SetScreenBlack();

        // Show the start prompt
        ShowStartPrompt();
    }

    void ShowStartPrompt()
    {
        instructionText.text = "Press any button to start the experiment.";
    }

    void Update()
    {
        // Wait for any key press to start the experiment
        if (!experimentStarted && Input.anyKeyDown)
        {
            experimentStarted = true;
            instructionText.text = ""; // Clear the prompt
            StartCoroutine(RunExperiment()); // Start the experiment
        }
    }

    void ParseCommandLineArguments()
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "-colorInput" && i + 1 < args.Length)
            {
                colorInputFileName = args[i + 1];
            }
            if (args[i] == "-input" && i + 1 < args.Length)
            {
                recordInputFileName = args[i + 1];
            }
            if (args[i] == "-output" && i + 1 < args.Length)
            {
                outputFileName = args[i + 1];
            }
        }

        Debug.Log($"Color Input File: {colorInputFileName}");
        Debug.Log($"Record Input File: {recordInputFileName}");
        Debug.Log($"Output File: {outputFileName}");
    }

    void LoadTrials(string filePath, bool isRecordFile)
    {
        if (!File.Exists(filePath))
        {
            Debug.LogError("Colors file not found: " + filePath);
            return;
        }

        string[] lines = File.ReadAllLines(filePath);
        foreach (string line in lines)
        {
            string[] values = line.Split(',');
            if (values.Length == 15)
            {
                // Using Color32 which takes 0-255 values directly
                Color32 bg1 = new Color32(
                    byte.Parse(values[0]),
                    byte.Parse(values[1]),
                    byte.Parse(values[2]),
                    160);
                    
                Color32 bg2 = new Color32(
                    byte.Parse(values[3]),
                    byte.Parse(values[4]),
                    byte.Parse(values[5]),
                    160);
                    
                Color32 sq1 = new Color32(
                    byte.Parse(values[6]),
                    byte.Parse(values[7]),
                    byte.Parse(values[8]),
                    255);
                    
                Color32 sq2 = new Color32(
                    byte.Parse(values[9]),
                    byte.Parse(values[10]),
                    byte.Parse(values[11]),
                    255);
                    
                int orderNumber = int.Parse(values[12]);
                int referencePosition = int.Parse(values[13]);
                int expectedResponse = int.Parse(values[14]);
                
                if (isRecordFile)
                {
                    recordTrials.Add(new Trial(bg1, bg2, sq1, sq2, orderNumber, referencePosition, expectedResponse));
                }
                else
                {
                    trials.Add(new Trial(bg1, bg2, sq1, sq2, orderNumber, referencePosition, expectedResponse));
                }
            }
        }
    }

    IEnumerator RunExperiment()
    {
        int totalTrials = trials.Count;
        int breakPoint1 = totalTrials / 3; // Break after 1/3 of trials
        int breakPoint2 = 2 * totalTrials / 3; // Break after 2/3 of trials
   
        while (currentTrialIndex < trials.Count)
        {
            // Check if it's time for a break
            if (currentTrialIndex == breakPoint1 || currentTrialIndex == breakPoint2)
            {
                // Start break
                instructionText.text = "Take a 1-minute break.";
                yield return new WaitForSeconds(60f); // 1-minute break

                // Wait for key press to resume
                instructionText.text = "Press any key to resume.";
                yield return new WaitUntil(() => Input.anyKeyDown);
                instructionText.text = ""; // Clear the prompt
            }
            
            // Display black screen before trial
            SetScreenBlack();
            yield return new WaitForSeconds(ITI);

            // Show trial
            ShowStimulus(1);
            yield return new WaitForSeconds(trialDuration);

            // Black screen between stimuli
            SetScreenBlack();
            yield return new WaitForSeconds(ISI);

            // Show second stimulus
            Debug.Log("Showing second stimulus");
            ShowStimulus(2);
            yield return new WaitForSeconds(trialDuration);

            // Turn screen black after trial
            SetScreenBlack();

            // Wait for user response
            yield return StartCoroutine(WaitForResponse());

            currentTrialIndex++;
        }

        EndExperiment();
    }

    void ShowStimulus(int stimulusNumber)
    {
        Trial currentTrial = trials[currentTrialIndex];

        if (stimulusNumber == 1)
        {
            background.GetComponent<Image>().color = currentTrial.Background1;
            square.GetComponent<Image>().color = currentTrial.Square1;
            instructionText.text = "";
        }
        else
        {
            background.GetComponent<Image>().color = currentTrial.Background2;
            square.GetComponent<Image>().color = currentTrial.Square2;
            instructionText.text = "";
        }
    }

    void SetScreenBlack()
    {
        // Changed to use Image component just like the squares
        background.GetComponent<Image>().color = Color.black;
        square.GetComponent<Image>().color = Color.black;
        instructionText.text = "";
    }

    IEnumerator WaitForResponse()
    {
        bool responseReceived = false;
        while (!responseReceived)
        {
            // Check for LB (Button 4) and RB (Button 5) presses
            if (Input.GetKeyDown(KeyCode.JoystickButton4)) // LB button
            {
                RecordResponse(1); // Record response for response "Same"
                responseReceived = true;
            }
            else if (Input.GetKeyDown(KeyCode.JoystickButton5)) // RB button
            {
                RecordResponse(2); // Record response for response "Different"
                responseReceived = true;
            }

            yield return null;
        }
    }

    void RecordResponse(int choice)
    {
        Trial currentTrial = trials[currentTrialIndex];
        Trial recordTrial = recordTrials[currentTrialIndex];
        string result = $"{currentTrial.OrderNumber}, {currentTrial.ReferencePosition}, {currentTrial.ExpectedResponse}, {choice}, {recordTrial.Square1}, {recordTrial.Background1}, {recordTrial.Square2}, {recordTrial.Background2}";
        File.AppendAllText(outputFileName, result + "\n");

        // // Play feedback sound
        // if (choice == currentTrial.ExpectedResponse)
        // {
        //     GenerateBeep(beepFrequency, 0.5f); // Generate a 0.5-second beep
        //     beepAudioSource.Play();
        // }
        // else
        // {
        //     GenerateNoise(0.5f); // Generate 0.5 seconds of noise
        //     noiseAudioSource.Play();
        // }
    }

    void GenerateBeep(float frequency, float duration)
    {
        int samples = (int)(duration * samplingFrequency);
        float[] data = new float[samples];
        for (int i = 0; i < samples; i++)
        {
            data[i] = Mathf.Sin(2 * Mathf.PI * frequency * i / samplingFrequency);
        }

        AudioClip beepClip = AudioClip.Create("Beep", samples, 1, (int)samplingFrequency, false);
        beepClip.SetData(data, 0);
        beepAudioSource.clip = beepClip;
    }

    void GenerateNoise(float duration)
    {
        int samples = (int)(duration * samplingFrequency);
        float[] data = new float[samples];
        for (int i = 0; i < samples; i++)
        {
            data[i] = UnityEngine.Random.Range(-1f, 1f); // Random noise
        }

        AudioClip noiseClip = AudioClip.Create("Noise", samples, 1, (int)samplingFrequency, false);
        noiseClip.SetData(data, 0);
        noiseAudioSource.clip = noiseClip;
    }

    void EndExperiment()
    {
        instructionText.text = "Experiment complete. Thank you!";
        Application.Quit();
    }
}

public class Trial
{
    public Color32 Background1;
    public Color32 Background2;
    public Color32 Square1;
    public Color32 Square2;
    public int OrderNumber;
    public int ReferencePosition;
    public int ExpectedResponse;

    public Trial(Color32 bg1, Color32 bg2, Color32 sq1, Color32 sq2, int orderNumber, int referencePosition, int expectedResponse)
    {
        Background1 = bg1;
        Background2 = bg2;
        Square1 = sq1;
        Square2 = sq2;
        OrderNumber = orderNumber;
        ReferencePosition = referencePosition;
        ExpectedResponse = expectedResponse;
    }
}